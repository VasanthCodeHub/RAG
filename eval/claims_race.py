"""Race the claims agent against the fixed workflow (requirement 3 of
task.md) over the same 10 synthetic claims (eval.claims_data.CLAIMS).

Reports, per system: pass rate, p50 latency, total tokens, cost/claim --
written to eval/claims_race.csv (8 numbers) and printed as a table. Also
writes eval/claims_budget_log.txt with one example of the agent hitting a
budget and terminating cleanly (requirement 4).

Run from the project root:
    .venv/Scripts/python.exe -m eval.claims_race
"""

import csv
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

from eval.claims_agent import run_agent
from eval.claims_data import CLAIMS
from eval.claims_tools import ClaimsLLM
from eval.claims_workflow import run_workflow

load_dotenv()

RACE_CSV_PATH = os.path.join(os.path.dirname(__file__), "claims_race.csv")
BUDGET_LOG_PATH = os.path.join(os.path.dirname(__file__), "claims_budget_log.txt")


def summarize(results: list[dict]) -> dict:
    latencies = [r["latency_ms"] for r in results]
    return {
        "pass_rate": sum(r["passed"] for r in results) / len(results),
        "p50_latency_ms": statistics.median(latencies),
        "total_tokens": sum(r["total_tokens"] for r in results),
        "cost_per_claim": sum(r["cost_usd"] for r in results) / len(results),
    }


def write_budget_log(agent_results: list[dict]) -> None:
    example = next((r for r in agent_results if r["status"] == "budget_exceeded"), None)
    with open(BUDGET_LOG_PATH, "w", encoding="utf-8") as f:
        if example is None:
            f.write("No agent run hit a budget in this run (none of the 10 claims triggered one).\n")
            return
        f.write(f"claims_agent claim_id={example['claim_id']} status=budget_exceeded "
                f"budget={example['budget_exceeded']} iterations_used={example['iterations_used']} "
                f"total_tokens={example['total_tokens']} cost_usd={example['cost_usd']:.5f} "
                f"latency_ms={example['latency_ms']:.1f}\n\n")
        f.write("Tool calls made before termination:\n")
        for entry in example["tool_log"]:
            f.write(f"  [{entry['iteration']}] {entry['tool']}({entry['args']}) -> {entry['result']}\n")
        f.write(
            "\nThe run stopped cleanly here instead of spinning: max_iterations was reached "
            "before compute_payout could be called, so the loop returned a budget_exceeded "
            "result rather than forcing a 3rd tool call.\n"
        )


def main():
    llm = ClaimsLLM()
    agent_results, workflow_results = [], []

    print(f"{'claim_id':<10} {'system':<9} {'pass':<6} {'disposition':<10} {'payout':>8} {'iters':>6} {'tokens':>7} {'cost_usd':>9} {'latency_ms':>11}")
    for claim in CLAIMS:
        claim_id = claim["claim_id"]
        agent_result = run_agent(claim_id, llm)
        workflow_result = run_workflow(claim_id, llm)
        agent_results.append(agent_result)
        workflow_results.append(workflow_result)
        for label, r in (("agent", agent_result), ("workflow", workflow_result)):
            print(f"{claim_id:<10} {label:<9} {str(r['passed']):<6} {str(r['disposition']):<10} "
                  f"{str(r['payout']):>8} {r['iterations_used']:>6} {r['total_tokens']:>7} "
                  f"{r['cost_usd']:>9.5f} {r['latency_ms']:>11.1f}")

    agent_summary = summarize(agent_results)
    workflow_summary = summarize(workflow_results)

    print("\n=== RESULT: 4 numbers per system ===\n")
    print(f"{'system':<10}{'pass_rate':>12}{'p50_latency_ms':>17}{'total_tokens':>14}{'cost_per_claim':>16}")
    for label, s in (("agent", agent_summary), ("workflow", workflow_summary)):
        print(f"{label:<10}{s['pass_rate']:>12.0%}{s['p50_latency_ms']:>17.1f}{s['total_tokens']:>14}{s['cost_per_claim']:>16.5f}")

    with open(RACE_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["system", "pass_rate", "p50_latency_ms", "total_tokens", "cost_per_claim"])
        for label, s in (("agent", agent_summary), ("workflow", workflow_summary)):
            writer.writerow([label, f"{s['pass_rate']:.4f}", f"{s['p50_latency_ms']:.1f}",
                              s["total_tokens"], f"{s['cost_per_claim']:.5f}"])
    print(f"\nWrote {RACE_CSV_PATH}")

    write_budget_log(agent_results)
    print(f"Wrote {BUDGET_LOG_PATH}")


if __name__ == "__main__":
    main()
