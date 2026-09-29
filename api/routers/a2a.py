"""A2A JSON-RPC endpoints for a manager and its document research agents."""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from a2a.protocol import AGENTS, agent_card, message_text, task_response

logger = logging.getLogger("api.a2a")
router = APIRouter(tags=["a2a"])
QUALITY_RANK = {"no_relevant_match": 0, "weak_match": 1, "strong_match": 2}


def _api_base_url() -> str:
    return os.getenv("SIMPLE_RAG_API_URL", "http://localhost:8000").rstrip("/")


class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"]
    id: str | int
    method: str
    params: dict[str, Any]


def _jsonrpc_error(request_id: str | int, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_result(wrapper: dict[str, Any]) -> dict[str, Any]:
    parsed = wrapper.get("parsed")
    if wrapper.get("is_error") or not isinstance(parsed, dict) or parsed.get("error"):
        message = parsed.get("error") if isinstance(parsed, dict) else wrapper.get("raw_text")
        raise RuntimeError(f"MCP ask_pdf failed: {message or 'empty response'}")
    if not parsed.get("answer") or not isinstance(parsed.get("quality_signal"), dict):
        raise RuntimeError("MCP ask_pdf returned an incomplete result.")
    return parsed


async def _ask_mcp(pdf_hash: str, question: str) -> dict[str, Any]:
    from ui.mcp_client import call_tool

    wrapper = await asyncio.to_thread(
        call_tool, "ask_pdf", {"pdf_hash": pdf_hash, "question": question}
    )
    return _tool_result(wrapper)


async def _send_to_agent(agent_name: str, pdf_hash: str, question: str, context_id: str) -> dict[str, Any]:
    request_id = uuid.uuid4().hex
    body = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "messageId": uuid.uuid4().hex,
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": json.dumps({"pdf_hash": pdf_hash, "question": question}),
                    }
                ],
                "contextId": context_id,
            }
        },
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(f"{_api_base_url()}/a2a/{agent_name}", json=body)
        response.raise_for_status()
        rpc = response.json()
    if rpc.get("error"):
        raise RuntimeError(f"A2A {agent_name} failed: {rpc['error'].get('message', 'unknown error')}")
    task = rpc.get("result", {})
    artifact_parts = [
        part.get("text")
        for artifact in task.get("artifacts", [])
        for part in artifact.get("parts", [])
        if part.get("kind") == "text"
    ]
    if not artifact_parts:
        raise RuntimeError(f"A2A {agent_name} returned no text artifact.")
    try:
        return json.loads(artifact_parts[0])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"A2A {agent_name} returned invalid result JSON.") from exc


def _usage(results: list[dict[str, Any]]) -> dict[str, Any]:
    prompt_tokens = 0
    completion_tokens = 0
    estimated_cost = 0.0
    token_data_available = True
    cost_data_available = True
    for result in results:
        usage = result.get("usage")
        if not isinstance(usage, dict):
            token_data_available = False
            cost_data_available = False
            continue
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
        cost = usage.get("estimated_cost_usd")
        if prompt is None or completion is None:
            token_data_available = False
        else:
            prompt_tokens += int(prompt)
            completion_tokens += int(completion)
        if cost is None:
            cost_data_available = False
        else:
            estimated_cost += float(cost)
    return {
        "prompt_tokens": prompt_tokens if token_data_available else None,
        "completion_tokens": completion_tokens if token_data_available else None,
        "total_tokens": prompt_tokens + completion_tokens if token_data_available else None,
        "estimated_cost_usd": estimated_cost if cost_data_available else None,
    }


def _metrics(team: dict[str, Any], solo: dict[str, Any], team_ms: float, solo_ms: float) -> dict[str, Any]:
    specialist_results = [team["document_answer"], team["evidence_review"]]
    team_quality = sum(
        QUALITY_RANK.get(result.get("quality_signal", {}).get("label"), 0)
        for result in specialist_results
    ) / len(specialist_results)
    solo_quality = QUALITY_RANK.get(solo.get("quality_signal", {}).get("label"), 0)
    team_usage = _usage(specialist_results)
    solo_usage = _usage([solo])

    if team_quality != solo_quality:
        winner = "A2A team" if team_quality > solo_quality else "Single MCP agent"
        reason = "Higher retrieved-evidence quality is the primary comparison."
    elif team_usage["estimated_cost_usd"] is not None and solo_usage["estimated_cost_usd"] is not None and team_usage["estimated_cost_usd"] != solo_usage["estimated_cost_usd"]:
        winner = "A2A team" if team_usage["estimated_cost_usd"] < solo_usage["estimated_cost_usd"] else "Single MCP agent"
        reason = "Quality tied; lower estimated model cost wins."
    elif team_ms != solo_ms:
        winner = "A2A team" if team_ms < solo_ms else "Single MCP agent"
        reason = "Quality tied; cost tied or unavailable; lower wall-clock latency wins."
    else:
        winner = "Tie"
        reason = "Quality, cost, and latency are tied or unavailable."

    return {
        "team": {
            "quality_score": team_quality,
            "quality_label": "strong_match" if team_quality >= 2 else "weak_match" if team_quality > 0 else "no_relevant_match",
            "latency_ms": round(team_ms, 1),
            **team_usage,
        },
        "single": {
            "quality_score": solo_quality,
            "quality_label": solo.get("quality_signal", {}).get("label", "unknown"),
            "latency_ms": round(solo_ms, 1),
            **solo_usage,
        },
        "winner": winner,
        "verdict_reason": reason,
    }


async def _run_manager(pdf_hash: str, question: str) -> dict[str, Any]:
    context_id = uuid.uuid4().hex

    async def timed_agent(agent_name: str, prompt: str) -> tuple[dict[str, Any], float]:
        start = time.perf_counter()
        result = await _send_to_agent(agent_name, pdf_hash, prompt, context_id)
        return result, (time.perf_counter() - start) * 1000

    async def timed_team() -> tuple[tuple[tuple[dict[str, Any], float], tuple[dict[str, Any], float]], float]:
        start = time.perf_counter()
        answer_task = timed_agent(
            "document-answer",
            f"Answer this question directly from the document. State when the document lacks the answer.\n\nQuestion: {question}",
        )
        evidence_task = timed_agent(
            "evidence-reviewer",
            f"Independently review the document for evidence answering this question. Focus on supporting details, qualifications, exceptions, and uncertainty.\n\nQuestion: {question}",
        )
        specialists = await asyncio.gather(answer_task, evidence_task)
        return (specialists[0], specialists[1]), (time.perf_counter() - start) * 1000

    async def timed_solo() -> tuple[dict[str, Any], float]:
        start = time.perf_counter()
        result = await _ask_mcp(pdf_hash, question)
        return result, (time.perf_counter() - start) * 1000

    team_run = await timed_team()
    solo_run = await timed_solo()
    (team_result, evidence_result), team_ms = team_run
    solo_result, solo_ms = solo_run
    team_answer, team_agent_ms = team_result
    evidence_answer, evidence_agent_ms = evidence_result

    team = {
        "answer": (
            f"**Direct finding**\n\n{team_answer['answer']}\n\n"
            f"**Independent evidence review**\n\n{evidence_answer['answer']}"
        ),
        "document_answer": team_answer,
        "evidence_review": evidence_answer,
        "delegations": [
            {"agent": "document-answer", "task": "Find and answer the question", "latency_ms": round(team_agent_ms, 1)},
            {"agent": "evidence-reviewer", "task": "Check supporting evidence and caveats", "latency_ms": round(evidence_agent_ms, 1)},
        ],
    }
    return {
        "question": question,
        "pdf_hash": pdf_hash,
        "team": team,
        "single": solo_result,
        "metrics": _metrics(team, solo_result, team_ms, solo_ms),
        "a2a_context_id": context_id,
    }


async def _handle(agent_name: str, request: JsonRpcRequest) -> dict[str, Any]:
    if request.method != "message/send":
        return _jsonrpc_error(request.id, -32601, "Only the A2A message/send method is supported.")
    try:
        text = message_text(request.params.get("message"))
        if len(text) > 6000:
            return _jsonrpc_error(request.id, -32602, "Message text exceeds the 6000-character limit.")
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("message must contain a JSON object")
        pdf_hash = payload.get("pdf_hash")
        question = payload.get("question")
        if not isinstance(pdf_hash, str) or not pdf_hash.strip():
            raise ValueError("pdf_hash is required")
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            raise ValueError("question must contain 1 to 2000 characters")

        if agent_name == "manager":
            result = await _run_manager(pdf_hash.strip(), question.strip())
        else:
            result = await _ask_mcp(pdf_hash.strip(), question.strip())
        context_id = request.params.get("message", {}).get("contextId")
        return {"jsonrpc": "2.0", "id": request.id, "result": task_response(result, context_id)}
    except ValueError as exc:
        return _jsonrpc_error(request.id, -32602, str(exc))
    except Exception as exc:
        logger.exception("A2A request failed agent=%s", agent_name)
        return _jsonrpc_error(request.id, -32000, str(exc))


@router.get("/.well-known/agent-card.json")
def manager_agent_card() -> dict[str, Any]:
    return agent_card("manager", _api_base_url())


@router.get("/a2a/agents")
def list_agents() -> list[dict[str, Any]]:
    return [agent_card(name, _api_base_url()) for name in AGENTS]


@router.get("/a2a/{agent_name}/.well-known/agent-card.json")
def specialist_agent_card(agent_name: str) -> dict[str, Any]:
    if agent_name not in AGENTS:
        raise HTTPException(status_code=404, detail="Unknown A2A agent.")
    return agent_card(agent_name, _api_base_url())


@router.post("/a2a/{agent_name}")
async def run_agent(agent_name: str, request: JsonRpcRequest) -> dict[str, Any]:
    if agent_name not in AGENTS:
        return _jsonrpc_error(request.id, -32601, "Unknown A2A agent.")
    return await _handle(agent_name, request)
