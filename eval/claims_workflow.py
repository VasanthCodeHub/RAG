"""Fixed, hard-coded claims-triage workflow (requirement 2 of task.md).

Same inputs, same 3 tools, same model, same output contract as
eval.claims_agent.run_agent -- but the tool sequence and disposition are
decided by plain Python, not an LLM loop. No budgets to enforce here because
there's no open-ended decision-making to bound: the path is fixed at
2 or 3 tool calls depending on the claim, deterministically, every time.
"""

import time

from eval.claims_data import CLAIMS_BY_ID, TRIGGER_KEYWORDS
from eval.claims_tools import ClaimsLLM, UsageTracker, compute_payout, explain, get_claim, search_policy


# Negation cues checked just before a keyword match, e.g. "no flooding
# involved" should NOT trigger the "flood" exclusion check.
_NEGATIONS = ("no ", "not ", "without ", "n't ", "never ")


def _detect_trigger_peril(notes: str) -> str | None:
    lowered = notes.lower()
    for keyword in TRIGGER_KEYWORDS:
        idx = lowered.find(keyword)
        if idx == -1:
            continue
        window = lowered[max(0, idx - 12):idx]
        if any(neg in window for neg in _NEGATIONS):
            continue
        return keyword
    return None


def run_workflow(claim_id: str, llm: ClaimsLLM) -> dict:
    start = time.perf_counter()
    tracker = UsageTracker()
    tool_log: list[dict] = []

    claim_record = get_claim(claim_id)
    tool_log.append({"iteration": 1, "tool": "get_claim", "args": {"claim_id": claim_id}, "result": claim_record})

    if claim_record["status"] == "denied":
        disposition = "denied"
    else:
        peril = _detect_trigger_peril(claim_record["adjuster_notes"])
        if peril:
            policy_result = search_policy(peril)
            tool_log.append({"iteration": 2, "tool": "search_policy", "args": {"peril": peril}, "result": policy_result})
            disposition = "excluded" if policy_result["excluded"] else "approved"
        else:
            disposition = "approved"

    payout_result = compute_payout(claim_id, disposition)
    tool_log.append({
        "iteration": len(tool_log) + 1,
        "tool": "compute_payout",
        "args": {"claim_id": claim_id, "disposition": disposition},
        "result": payout_result,
    })

    claim = CLAIMS_BY_ID[claim_id]
    payout = payout_result["payout"]
    explanation = explain(llm, tracker, claim, disposition, payout)

    passed = disposition == claim["expected_disposition"] and payout == claim["expected_payout"]
    return {
        "claim_id": claim_id,
        "status": "ok",
        "budget_exceeded": None,
        "passed": passed,
        "disposition": disposition,
        "payout": payout,
        "explanation": explanation,
        "tool_log": tool_log,
        "iterations_used": len(tool_log),
        "total_tokens": tracker.total_tokens,
        "cost_usd": tracker.cost_usd,
        "latency_ms": (time.perf_counter() - start) * 1000,
    }


def main():
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from dotenv import load_dotenv

    load_dotenv()

    llm = ClaimsLLM()
    for claim_id in ("CLM-1001", "CLM-1003"):
        result = run_workflow(claim_id, llm)
        print(f"\n=== {claim_id} ===")
        for key, value in result.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
