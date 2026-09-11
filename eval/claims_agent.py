"""Budgeted ReAct-style claims-triage agent (requirement 1 + 4 of task.md).

One "iteration" = one LLM turn that decides which tool to call next. The
agent gets at most `max_iterations` of those before it must have already
called `compute_payout`; if it hasn't, the run terminates cleanly (no crash,
no silent retry loop) with `status="budget_exceeded"`. All 4 budgets --
max_iterations, max_tokens, max_cost_usd, max_wall_clock_s -- are checked on
every iteration.

Run standalone (prints one example run) with:
    .venv/Scripts/python.exe -m eval.claims_agent
"""

import json
import logging
import time

from eval.claims_data import CLAIMS_BY_ID
from eval.claims_tools import TOOL_FUNCS, TOOL_SCHEMAS, ClaimsLLM, UsageTracker, explain

logger = logging.getLogger("eval.claims_agent")

DEFAULT_MAX_ITERATIONS = 2  # per spec: race agent vs workflow with this budget
DEFAULT_MAX_TOKENS = 4000
DEFAULT_MAX_COST_USD = 0.02
DEFAULT_MAX_WALL_CLOCK_S = 20.0

SYSTEM_PROMPT = """You are a claims-triage assistant. You are given a claim_id and must \
decide its disposition (approved, denied, or excluded) and its payout, using only the \
available tools. Call exactly one tool per turn.

Rules, in order:
1. Always call get_claim first. Never skip this.
2. If get_claim's status is already "denied", the disposition is "denied" -- go straight \
to compute_payout with disposition="denied".
3. Otherwise, read the adjuster_notes. If they mention a specific peril or circumstance \
that might not be covered (flood, wear and tear, driving under the influence / DUI, \
business or commercial use, intentional damage), you MUST call search_policy with that \
peril before deciding -- never guess whether something is excluded.
4. If the notes describe only an ordinary covered loss (collision, fire, theft, storm, \
glass/windshield, burglary) with none of the perils in rule 3, skip search_policy and use \
disposition="approved".
5. Once you know the disposition, call compute_payout exactly once with the claim_id and \
disposition, then stop."""


def _terminate(reason: str, claim_id: str, tool_log: list, tracker: UsageTracker, start: float) -> dict:
    logger.warning(
        "claims_agent claim_id=%s status=budget_exceeded budget=%s iterations_used=%d "
        "total_tokens=%d cost_usd=%.5f elapsed_s=%.2f",
        claim_id, reason, len(tool_log), tracker.total_tokens, tracker.cost_usd,
        time.perf_counter() - start,
    )
    return {
        "claim_id": claim_id,
        "status": "budget_exceeded",
        "budget_exceeded": reason,
        "passed": False,
        "disposition": None,
        "payout": None,
        "explanation": None,
        "tool_log": tool_log,
        "iterations_used": len(tool_log),
        "total_tokens": tracker.total_tokens,
        "cost_usd": tracker.cost_usd,
        "latency_ms": (time.perf_counter() - start) * 1000,
    }


def run_agent(
    claim_id: str,
    llm: ClaimsLLM,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_cost_usd: float = DEFAULT_MAX_COST_USD,
    max_wall_clock_s: float = DEFAULT_MAX_WALL_CLOCK_S,
) -> dict:
    start = time.perf_counter()
    tracker = UsageTracker()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Process claim {claim_id}."},
    ]
    tool_log: list[dict] = []
    compute_result = None

    for iteration in range(1, max_iterations + 1):
        if time.perf_counter() - start > max_wall_clock_s:
            return _terminate("max_wall_clock_s", claim_id, tool_log, tracker, start)

        response = llm.chat(messages, tools=TOOL_SCHEMAS)
        tracker.add(response.usage)

        if tracker.total_tokens > max_tokens:
            return _terminate("max_tokens", claim_id, tool_log, tracker, start)
        if tracker.cost_usd > max_cost_usd:
            return _terminate("max_cost_usd", claim_id, tool_log, tracker, start)

        message = response.choices[0].message
        if not message.tool_calls:
            # Model tried to answer directly without calling compute_payout.
            # Treat as incomplete -- the output contract requires a tool-computed payout.
            break

        call = message.tool_calls[0]
        name = call.function.name
        try:
            args = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        func = TOOL_FUNCS.get(name)
        result = func(**args) if func else {"error": f"unknown tool: {name!r}"}
        tool_log.append({"iteration": iteration, "tool": name, "args": args, "result": result})

        messages.append({"role": "assistant", "content": message.content, "tool_calls": [call]})
        messages.append({"role": "tool", "tool_call_id": call.id, "name": name, "content": json.dumps(result)})

        if name == "compute_payout" and "error" not in result:
            compute_result = result
            break

    if compute_result is None:
        return _terminate("max_iterations", claim_id, tool_log, tracker, start)

    claim = CLAIMS_BY_ID[claim_id]
    disposition = compute_result["disposition"]
    payout = compute_result["payout"]
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
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    llm = ClaimsLLM()
    for claim_id in ("CLM-1001", "CLM-1003"):
        result = run_agent(claim_id, llm)
        print(f"\n=== {claim_id} ===")
        for key, value in result.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
