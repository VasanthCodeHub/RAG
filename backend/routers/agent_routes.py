"""HTTP surface for the single agents: the generic document agent and the
claims-triage demo agent (race vs workflow, trajectory review, injection test).
"""

import os
import statistics

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent.claims_agent import run_agent
from agent.claims_data import CLAIMS, INJECTION_CLAIM
from agent.claims_tools import ClaimsLLM
from agent.claims_workflow import run_workflow
from agent.document_agent import mcp_search, run_document_agent
from eval.claims_injection_eval import attack_succeeded
from eval.claims_trajectory_eval import EVAL_MAX_ITERATIONS, expected_trajectory, run_batch, summarize

router = APIRouter(prefix="/agent", tags=["agent"])


def _llm() -> ClaimsLLM:
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(status_code=400, detail="GROQ_API_KEY is not set on the server.")
    return ClaimsLLM()


class DocumentAgentRequest(BaseModel):
    pdf_hash: str
    question: str = Field(min_length=1, max_length=2000)


@router.post("/document")
def document_agent(req: DocumentAgentRequest):
    return run_document_agent(req.question, _llm(), mcp_search(req.pdf_hash))


def _race_summary(results: list[dict]) -> dict:
    return {
        "pass_rate": sum(r["passed"] for r in results) / len(results),
        "p50_latency_ms": statistics.median([r["latency_ms"] for r in results]),
        "total_tokens": sum(r["total_tokens"] for r in results),
        "cost_per_claim": sum(r["cost_usd"] for r in results) / len(results),
    }


@router.get("/claims")
def claims():
    return CLAIMS


@router.post("/claims/race")
def claims_race():
    llm = _llm()
    agent_results = [run_agent(c["claim_id"], llm) for c in CLAIMS]
    workflow_results = [run_workflow(c["claim_id"], llm) for c in CLAIMS]
    return {
        "claims": CLAIMS,
        "agent": agent_results,
        "workflow": workflow_results,
        "agent_summary": _race_summary(agent_results),
        "workflow_summary": _race_summary(workflow_results),
    }


@router.post("/claims/trajectory")
def claims_trajectory():
    llm = _llm()
    before = run_batch(llm, guarded=False)
    after = run_batch(llm, guarded=True)
    return {
        "max_iterations": EVAL_MAX_ITERATIONS,
        "before": before,
        "after": after,
        "before_summary": summarize(before),
        "after_summary": summarize(after),
        "expected": {c["claim_id"]: expected_trajectory(c) for c in CLAIMS},
        "claims": CLAIMS,
    }


@router.post("/claims/injection")
def claims_injection():
    llm = _llm()
    before = run_agent(INJECTION_CLAIM["claim_id"], llm, max_iterations=EVAL_MAX_ITERATIONS, guarded=False)
    after = run_agent(INJECTION_CLAIM["claim_id"], llm, max_iterations=EVAL_MAX_ITERATIONS, guarded=True)
    return {
        "claim": INJECTION_CLAIM,
        "before": {**before, "attack_succeeded": attack_succeeded(before)},
        "after": {**after, "attack_succeeded": attack_succeeded(after)},
    }
