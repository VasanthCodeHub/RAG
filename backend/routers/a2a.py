"""A2A JSON-RPC endpoints for a manager and its document research agents."""

import json
import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from a2a.manager import _api_base_url, _ask_mcp, _run_manager
from a2a.protocol import AGENTS, agent_card, message_text, task_response

logger = logging.getLogger("api.a2a")
router = APIRouter(tags=["a2a"])


class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"]
    id: str | int
    method: str
    params: dict[str, Any]


def _jsonrpc_error(request_id: str | int, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


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
