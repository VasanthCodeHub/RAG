"""Week 8 -- trajectory evaluation for the claims agent.

Requirement: "Look at a batch of your agent's runs and find where it took a
wrong path even when the answer looked right" (the outcome-vs-trajectory
gap), then "fix your top failure -- measuring the improvement."

For each of the 10 Week 7 claims (eval.claims_data.CLAIMS) this script:

1. Derives the GROUND-TRUTH expected tool sequence from the claim's own
   status/notes (independent of what the model does):
     - status == "denied"          -> get_claim, compute_payout
     - notes raise an excludable peril -> get_claim, search_policy, compute_payout
     - otherwise (ordinary loss)   -> get_claim, compute_payout
2. Runs the agent TWICE per claim -- once with the Week 8 guard disabled
   (`guarded=False`, i.e. the plain Week 7 agent) and once with it enabled
   (`guarded=True`) -- with a generous max_iterations so a run is never cut
   short by budget, which would be confounded with a trajectory failure.
3. Compares the actual tool-call sequence to the expected one and flags the
   "outcome-vs-trajectory gap": passed=True (right final disposition/payout)
   but trajectory_match=False (wrong/incomplete path to get there --
   i.e. a right answer reached by luck that would not survive a harder
   input).
4. Reports tool-choice accuracy and gap count before vs after the guard, to
   measure the fix.

Run from the project root:
    .venv/Scripts/python.exe -m eval.claims_trajectory_eval
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

from eval.claims_agent import run_agent
from eval.claims_data import CLAIMS
from eval.claims_tools import ClaimsLLM, detect_trigger_peril

load_dotenv()

# Generous on purpose -- this eval measures trajectory correctness, not
# budget behaviour (that's Week 7's claims_race.py, which deliberately uses
# a tight max_iterations=2).
EVAL_MAX_ITERATIONS = 5

TRAJECTORY_CSV_PATH = os.path.join(os.path.dirname(__file__), "claims_trajectory.csv")


def expected_trajectory(claim: dict) -> list[str]:
    if claim["status"] == "denied":
        return ["get_claim", "compute_payout"]
    if detect_trigger_peril(claim["adjuster_notes"]):
        return ["get_claim", "search_policy", "compute_payout"]
    return ["get_claim", "compute_payout"]


def run_batch(llm: ClaimsLLM, guarded: bool) -> list[dict]:
    rows = []
    for claim in CLAIMS:
        result = run_agent(claim["claim_id"], llm, max_iterations=EVAL_MAX_ITERATIONS, guarded=guarded)
        actual = [entry["tool"] for entry in result["tool_log"]]
        expected = expected_trajectory(claim)
        trajectory_match = actual == expected
        gap = bool(result["passed"]) and not trajectory_match
        rows.append({
            "claim_id": claim["claim_id"],
            "guarded": guarded,
            "status": result["status"],
            "passed": result["passed"],
            "expected_trajectory": " -> ".join(expected),
            "actual_trajectory": " -> ".join(actual),
            "trajectory_match": trajectory_match,
            "outcome_vs_trajectory_gap": gap,
            "guard_events": result["guard_events"],
        })
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "outcome_pass_rate": sum(r["passed"] for r in rows) / n,
        "tool_choice_accuracy": sum(r["trajectory_match"] for r in rows) / n,
        "gap_count": sum(r["outcome_vs_trajectory_gap"] for r in rows),
        "gap_claims": [r["claim_id"] for r in rows if r["outcome_vs_trajectory_gap"]],
    }


def print_table(rows: list[dict]) -> None:
    print(f"{'claim_id':<10} {'passed':<7} {'match':<7} {'gap':<5} {'expected':<32} {'actual':<32}")
    for r in rows:
        print(f"{r['claim_id']:<10} {str(r['passed']):<7} {str(r['trajectory_match']):<7} "
              f"{str(r['outcome_vs_trajectory_gap']):<5} {r['expected_trajectory']:<32} {r['actual_trajectory']:<32}")


def main():
    llm = ClaimsLLM()

    print("=== BEFORE (guard disabled -- Week 7 agent as-is) ===")
    before_rows = run_batch(llm, guarded=False)
    print_table(before_rows)
    before_summary = summarize(before_rows)
    print(f"\noutcome_pass_rate={before_summary['outcome_pass_rate']:.0%} "
          f"tool_choice_accuracy={before_summary['tool_choice_accuracy']:.0%} "
          f"gap_count={before_summary['gap_count']} gap_claims={before_summary['gap_claims']}")

    print("\n=== AFTER (guard enabled -- Week 8 fix) ===")
    after_rows = run_batch(llm, guarded=True)
    print_table(after_rows)
    after_summary = summarize(after_rows)
    print(f"\noutcome_pass_rate={after_summary['outcome_pass_rate']:.0%} "
          f"tool_choice_accuracy={after_summary['tool_choice_accuracy']:.0%} "
          f"gap_count={after_summary['gap_count']} gap_claims={after_summary['gap_claims']}")

    with open(TRAJECTORY_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["claim_id", "guarded", "passed", "trajectory_match", "outcome_vs_trajectory_gap",
                          "expected_trajectory", "actual_trajectory"])
        for r in before_rows + after_rows:
            writer.writerow([r["claim_id"], r["guarded"], r["passed"], r["trajectory_match"],
                              r["outcome_vs_trajectory_gap"], r["expected_trajectory"], r["actual_trajectory"]])
    print(f"\nWrote {TRAJECTORY_CSV_PATH}")

    print("\n=== SUMMARY: before vs after ===")
    print(f"{'':<12}{'outcome_pass_rate':>20}{'tool_choice_accuracy':>23}{'gap_count':>12}")
    print(f"{'before':<12}{before_summary['outcome_pass_rate']:>20.0%}"
          f"{before_summary['tool_choice_accuracy']:>23.0%}{before_summary['gap_count']:>12}")
    print(f"{'after':<12}{after_summary['outcome_pass_rate']:>20.0%}"
          f"{after_summary['tool_choice_accuracy']:>23.0%}{after_summary['gap_count']:>12}")


if __name__ == "__main__":
    main()
