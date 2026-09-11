# Week 7 — Race the claims agent against a fixed workflow

Deliverables for task.md, Set D. Reproduce with:
`.venv/Scripts/python.exe -m eval.claims_race`

## 1. Race table (8 numbers)

| system   | pass_rate | p50_latency_ms | total_tokens | cost_per_claim |
|----------|-----------|----------------|--------------|-----------------|
| agent    | 60%       | 2240.6         | 16543        | $0.00037        |
| workflow | 100%      | 642.0          | 2427         | $0.00010        |

Full per-claim detail: `eval/claims_race.csv` (summary) and the console output of
`eval.claims_race` (per-claim rows: disposition, payout, iterations, tokens, cost, latency).

## 2. Budget-termination log (requirement 4)

From `eval/claims_budget_log.txt` — the agent on CLM-1003 (a flood claim):

```
claims_agent claim_id=CLM-1003 status=budget_exceeded budget=max_iterations iterations_used=2 total_tokens=1483 cost_usd=0.00029 latency_ms=1437.0

Tool calls made before termination:
  [1] get_claim({'claim_id': 'CLM-1003'}) -> {..., 'adjuster_notes': 'River overflowed after heavy rain; flood water entered the basement and ruined the flooring.'}
  [2] search_policy({'peril': 'flood'}) -> {'peril': 'flood', 'excluded': True, 'note': 'Flood damage is excluded under a standard policy; requires separate flood insurance.'}

The run stopped cleanly here instead of spinning: max_iterations was reached before
compute_payout could be called, so the loop returned a budget_exceeded result rather
than forcing a 3rd tool call.
```

All 4 budgets are enforced in `eval/claims_agent.py::run_agent` on every iteration
(`max_iterations=2`, `max_tokens=4000`, `max_cost_usd=0.02`, `max_wall_clock_s=20`).
In this run, `max_iterations` is the one that fires — the other three exist in code
and are checked every loop, but a 2-3 tool-call claims-triage task never gets close to
them at this model's price/latency.

## 3. Third tool description diff (requirement 1)

`compute_payout` is new — it did not exist before this week. `get_claim` and
`search_policy` are the two tools the loop already had.

```diff
+ {
+   "name": "compute_payout",
+   "description": "Compute the final payable amount for one claim given its
+     disposition, subtracting the policy deductible from the reported amount
+     (returns 0 for a denied or excluded claim). Call this exactly once, last,
+     after you have decided the claim's disposition -- never before.",
+   "parameters": {
+     "type": "object",
+     "properties": {
+       "claim_id": {"type": "string"},
+       "disposition": {"type": "string", "enum": ["approved", "denied", "excluded"]}
+     },
+     "required": ["claim_id", "disposition"]
+   }
+ }
```

One job (the payout arithmetic), an enum-typed `disposition` parameter, and no
wording overlap with `get_claim` (fetches the record) or `search_policy` (checks a
named peril against the exclusions list) — see `eval/claims_tools.py::TOOL_SCHEMAS`.

## 4. Verdict (requirement 5)

The fixed workflow passed 100% (10/10): p50 latency 642ms, 2,427 total tokens,
$0.00010/claim. The agent passed 60% (6/10): p50 2,241ms, 16,543 total tokens,
$0.00037/claim — worse on every number. The one input class where the path
genuinely varies — claims whose notes name a specific peril (flood, DUI,
wear-and-tear, business use) needing a policy-exclusion check before payout — is
exactly where the agent failed every time: that path needs 3 sequential tool
calls, and its max_iterations=2 budget cuts it off after the 2nd, before
compute_payout runs. The workflow handles that same branch with one hard-coded
keyword check, correctly and deterministically. So even the one class where the
decision path varies by input didn't need an agent — a plain conditional handled
it, faster and 3.5x cheaper. None of these 10 claims required an autonomous agent.

## Submission checklist

- [x] Agent and workflow both runnable by one command each (`python -m eval.claims_agent`, `python -m eval.claims_workflow`)
- [x] `eval/claims_race.csv` with all 8 numbers over the same 10 claims
- [x] `eval/claims_budget_log.txt` excerpt above, showing which budget fired
- [x] Diff of the third tool's description and parameter enum (section 3)
- [x] Verdict paragraph naming the claim class that does/doesn't need an agent (section 4)
