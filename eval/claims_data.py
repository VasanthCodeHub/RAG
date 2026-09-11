"""Synthetic insurance-claims fixture for the Week 7 agent-loop race
(see task.md and eval/claims_submission.md).

10 claims, each with a ground-truth `expected_disposition` /
`expected_payout` so a run (agent or workflow) can be graded as pass/fail.
4 of them are "dependent": the adjuster notes mention a specific peril
(flood, DUI, wear-and-tear, business use) that only `search_policy` can
confirm is excluded -- the correct tool sequence for those is genuinely
`get_claim -> search_policy -> compute_payout` (3 calls), not knowable in
advance from the claim alone. One (CLM-1007) is pre-denied via the claim's
own `status` field, exercising the "denied" disposition without any policy
lookup. The rest are ordinary covered losses.
"""

# Small curated exclusions knowledge base for the `search_policy` tool.
# Deliberately structured (not prose) -- this is a ~10-entry lookup table,
# not a document corpus, so a keyword/substring match is the right tool for
# it (reusing rag/retrieval.py's embedding search would be a mismatch for
# data this size and shape).
POLICY_EXCLUSIONS = [
    {"peril": "flood", "excluded": True,
     "note": "Flood damage is excluded under a standard policy; requires separate flood insurance."},
    {"peril": "driving under the influence", "excluded": True,
     "note": "Losses occurring while the policyholder was driving under the influence (DUI) are excluded."},
    {"peril": "wear and tear", "excluded": True,
     "note": "Gradual wear and tear / mechanical breakdown is excluded under standard auto and home policies."},
    {"peril": "business use", "excluded": True,
     "note": "Damage occurring while the vehicle was used for commercial/gig-economy purposes is excluded under a personal auto policy."},
    {"peril": "intentional damage", "excluded": True,
     "note": "Intentional or deliberate damage caused by the policyholder is excluded."},
    {"peril": "collision", "excluded": False,
     "note": "Collision damage is covered under comprehensive/collision coverage."},
    {"peril": "theft", "excluded": False,
     "note": "Theft is covered under comprehensive coverage."},
    {"peril": "fire", "excluded": False,
     "note": "Fire damage is covered under standard homeowners and auto policies."},
    {"peril": "storm", "excluded": False,
     "note": "Wind/storm damage is covered under standard homeowners policies."},
    {"peril": "glass", "excluded": False,
     "note": "Glass/windshield damage is covered, typically at a reduced deductible."},
]

# Peril keywords the FIXED WORKFLOW scans the adjuster notes for, to decide
# whether a `search_policy` check is needed before computing payout. The
# agent is given the same list in its system prompt (see claims_agent.py) so
# both systems are working from the same domain knowledge -- the difference
# being the workflow applies it deterministically in Python, the agent has
# to decide to use it via tool calls within its iteration budget.
TRIGGER_KEYWORDS = ["flood", "driving under the influence", "dui", "wear and tear", "business use", "intentional"]

CLAIMS = [
    {
        "claim_id": "CLM-1001",
        "claimant": "Priya Nair",
        "claim_type": "auto",
        "status": "under_review",
        "reported_amount": 4500,
        "deductible": 500,
        "adjuster_notes": "Rear-ended at a red light; other driver at fault confirmed by the police report. Vehicle is repairable.",
        "expected_disposition": "approved",
        "expected_payout": 4000,
        "dependent": False,
    },
    {
        "claim_id": "CLM-1002",
        "claimant": "Daniel Osei",
        "claim_type": "home",
        "status": "under_review",
        "reported_amount": 15000,
        "deductible": 1000,
        "adjuster_notes": "Kitchen fire caused smoke and structural damage to the ceiling. Fire department report attached.",
        "expected_disposition": "approved",
        "expected_payout": 14000,
        "dependent": False,
    },
    {
        "claim_id": "CLM-1003",
        "claimant": "Maria Santos",
        "claim_type": "home",
        "status": "under_review",
        "reported_amount": 20000,
        "deductible": 1000,
        "adjuster_notes": "River overflowed after heavy rain; flood water entered the basement and ruined the flooring.",
        "expected_disposition": "excluded",
        "expected_payout": 0,
        "dependent": True,
    },
    {
        "claim_id": "CLM-1004",
        "claimant": "Kevin Walsh",
        "claim_type": "auto",
        "status": "under_review",
        "reported_amount": 9000,
        "deductible": 1000,
        "adjuster_notes": "Single-vehicle crash into a guardrail; police report states the driver's BAC was over the legal limit (driving under the influence) at the time.",
        "expected_disposition": "excluded",
        "expected_payout": 0,
        "dependent": True,
    },
    {
        "claim_id": "CLM-1005",
        "claimant": "Ahmed Farouk",
        "claim_type": "auto",
        "status": "under_review",
        "reported_amount": 3200,
        "deductible": 500,
        "adjuster_notes": "Transmission failed on the highway; mechanic's report attributes it to normal wear and tear, no collision involved.",
        "expected_disposition": "excluded",
        "expected_payout": 0,
        "dependent": True,
    },
    {
        "claim_id": "CLM-1006",
        "claimant": "Grace Lin",
        "claim_type": "home",
        "status": "under_review",
        "reported_amount": 6000,
        "deductible": 500,
        "adjuster_notes": "Home burglarized while owners were on vacation; several electronics stolen, forced entry confirmed by the police report.",
        "expected_disposition": "approved",
        "expected_payout": 5500,
        "dependent": False,
    },
    {
        "claim_id": "CLM-1007",
        "claimant": "Robert Chen",
        "claim_type": "auto",
        "status": "denied",
        "reported_amount": 7000,
        "deductible": 500,
        "adjuster_notes": "Policyholder's premium payment was 45 days late; the policy had lapsed at the time of the accident.",
        "expected_disposition": "denied",
        "expected_payout": 0,
        "dependent": False,
    },
    {
        "claim_id": "CLM-1008",
        "claimant": "Fatima Al-Sayed",
        "claim_type": "home",
        "status": "under_review",
        "reported_amount": 10000,
        "deductible": 1000,
        "adjuster_notes": "Severe windstorm tore off part of the roof shingles; no flooding involved.",
        "expected_disposition": "approved",
        "expected_payout": 9000,
        "dependent": False,
    },
    {
        "claim_id": "CLM-1009",
        "claimant": "Liam O'Brien",
        "claim_type": "auto",
        "status": "under_review",
        "reported_amount": 800,
        "deductible": 500,
        "adjuster_notes": "Rock kicked up on the highway cracked the windshield; no other damage.",
        "expected_disposition": "approved",
        "expected_payout": 300,
        "dependent": False,
    },
    {
        "claim_id": "CLM-1010",
        "claimant": "Sofia Rossi",
        "claim_type": "auto",
        "status": "under_review",
        "reported_amount": 5000,
        "deductible": 500,
        "adjuster_notes": "Vehicle was being used to deliver food for a paid gig-economy job (business use) when the collision occurred.",
        "expected_disposition": "excluded",
        "expected_payout": 0,
        "dependent": True,
    },
]

CLAIMS_BY_ID = {c["claim_id"]: c for c in CLAIMS}
