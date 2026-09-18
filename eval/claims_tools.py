"""The 3 claims-triage tools (get_claim, search_policy -- presumed to already
exist per task.md; compute_payout -- the new 3rd tool for requirement 1) plus
a thin, usage-tracking Groq chat wrapper shared by the agent and the fixed
workflow.

Kept self-contained on purpose: does not import or modify rag/llm.py. The
tool functions are plain, deterministic Python -- the only thing that
differs between the agent (eval/claims_agent.py) and the fixed workflow
(eval/claims_workflow.py) is *what decides which tool to call, in what
order*.
"""

import os
import time

from groq import Groq

from eval.claims_data import CLAIMS_BY_ID, POLICY_EXCLUSIONS, TRIGGER_KEYWORDS

MODEL_NAME = "openai/gpt-oss-120b"

# Approximate Groq list price for openai/gpt-oss-120b at the time this was
# written (USD per token). Only used for relative agent-vs-workflow cost
# comparison here -- check Groq's current pricing page if exact accuracy
# matters for real billing.
PRICE_PER_PROMPT_TOKEN = 0.15 / 1_000_000
PRICE_PER_COMPLETION_TOKEN = 0.75 / 1_000_000


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def get_claim(claim_id: str) -> dict:
    """Fetch the full claim record: claimant, type, status, reported
    amount, deductible, and the adjuster's notes. Always call this first --
    it's the only source of the adjuster notes and the claim's status.
    """
    claim = CLAIMS_BY_ID.get(claim_id)
    if claim is None:
        return {"error": f"no such claim: {claim_id!r}"}
    return {
        "claim_id": claim["claim_id"],
        "claimant": claim["claimant"],
        "claim_type": claim["claim_type"],
        "status": claim["status"],
        "reported_amount": claim["reported_amount"],
        "deductible": claim["deductible"],
        "adjuster_notes": claim["adjuster_notes"],
    }


def search_policy(peril: str) -> dict:
    """Check whether a specific named peril or circumstance raised in the
    adjuster notes (e.g. flood, wear and tear, driving under the influence,
    business use) is excluded under the standard policy. Only call this
    when the notes raise a specific peril that needs verifying -- skip it
    for ordinary covered losses like collision, fire, theft, or storm
    damage.
    """
    needle = peril.strip().lower()
    for entry in POLICY_EXCLUSIONS:
        if entry["peril"] in needle or needle in entry["peril"]:
            return {"peril": entry["peril"], "excluded": entry["excluded"], "note": entry["note"]}
    return {"peril": peril, "excluded": False, "note": "No specific exclusion found for this peril; standard coverage applies."}


def compute_payout(claim_id: str, disposition: str) -> dict:
    """Compute the final payable amount for one claim given its disposition
    (approved / denied / excluded), subtracting the policy deductible from
    the reported amount -- 0 for a denied or excluded claim. Call this
    exactly once, last, after the disposition has been decided.
    """
    claim = CLAIMS_BY_ID.get(claim_id)
    if claim is None:
        return {"error": f"no such claim: {claim_id!r}"}
    if disposition in ("denied", "excluded"):
        payout = 0
    else:
        payout = max(claim["reported_amount"] - claim["deductible"], 0)
    return {"claim_id": claim_id, "disposition": disposition, "payout": payout}


# Negation cues checked just before a keyword match, e.g. "no flooding
# involved" should NOT trigger the "flood" exclusion check. Shared by the
# fixed workflow (eval/claims_workflow.py) and the Week 8 agent guard
# (eval/claims_agent.py) so both agree on when search_policy is required.
_NEGATIONS = ("no ", "not ", "without ", "n't ", "never ")


def detect_trigger_peril(notes: str) -> str | None:
    """Return the first excludable peril keyword mentioned in `notes` (and
    not negated), or None. This is the ground-truth check for "does this
    claim require a search_policy call" -- independent of whatever a model
    (or an injected instruction inside the notes) claims.
    """
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


TOOL_FUNCS = {
    "get_claim": get_claim,
    "search_policy": search_policy,
    "compute_payout": compute_payout,
}

# OpenAI-compatible tool schemas (Groq's `tools=` parameter uses this shape).
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_claim",
            "description": (
                "Fetch the full claim record (claimant, type, status, reported amount, "
                "deductible, and the adjuster's notes) for one claim by its ID. Always "
                "call this first for any claim -- it is the only source of the adjuster "
                "notes and the claim's status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string", "description": "The claim ID, e.g. 'CLM-1001'."},
                },
                "required": ["claim_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": (
                "Check whether a specific named peril or circumstance mentioned in the "
                "adjuster notes (e.g. flood, wear and tear, driving under the influence, "
                "business use) is excluded under the standard policy. Call this only when "
                "the notes raise a specific peril you need to verify before computing "
                "payout -- skip it for ordinary covered losses like collision, fire, "
                "theft, or storm damage."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "peril": {"type": "string", "description": "The peril or circumstance to check, e.g. 'flood'."},
                },
                "required": ["peril"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_payout",
            "description": (
                "Compute the final payable amount for one claim given its disposition, "
                "subtracting the policy deductible from the reported amount (returns 0 for "
                "a denied or excluded claim). Call this exactly once, last, after you have "
                "decided the claim's disposition -- never before."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string", "description": "The claim ID, e.g. 'CLM-1001'."},
                    "disposition": {
                        "type": "string",
                        "enum": ["approved", "denied", "excluded"],
                        "description": "The decided disposition for this claim.",
                    },
                },
                "required": ["claim_id", "disposition"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Thin usage-tracking Groq chat wrapper (shared by agent + workflow so
# token/cost accounting is computed identically for both).
# ---------------------------------------------------------------------------


class UsageTracker:
    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0

    def add(self, usage) -> None:
        if usage is None:
            return
        self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
        self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
        self.calls += 1

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def cost_usd(self) -> float:
        return self.prompt_tokens * PRICE_PER_PROMPT_TOKEN + self.completion_tokens * PRICE_PER_COMPLETION_TOKEN


class ClaimsLLM:
    """Direct Groq client wrapper with tool-calling support. Kept separate
    from rag.llm.GroqLLM, which has no tool-calling support and is used for
    the unrelated PDF-chat pipeline.
    """

    def __init__(self, api_key: str | None = None, model_name: str = MODEL_NAME):
        api_key = api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Please set GROQ_API_KEY environment variable or pass api_key.")
        self.client = Groq(api_key=api_key)
        self.model_name = model_name

    def chat(self, messages: list[dict], tools: list[dict] | None = None, max_retries: int = 3):
        """One raw chat-completion call. Returns the full response object
        (caller reads .choices[0].message and .usage).
        """
        kwargs = dict(model=self.model_name, messages=messages, temperature=0.0)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                return self.client.chat.completions.create(**kwargs)
            except Exception as error:  # noqa: BLE001 -- mirrors rag.llm.GroqLLM's retry pattern
                last_error = error
                time.sleep(0.5 * attempt)
        raise RuntimeError(f"Groq request failed after {max_retries} attempts") from last_error


EXPLANATION_PROMPT = (
    "Claim {claim_id} ({claim_type}) for {claimant}: reported amount ${reported_amount}, "
    "deductible ${deductible}. Disposition: {disposition}. Payout: ${payout}.\n"
    "Write one short, professional sentence explaining this decision to the claimant. "
    "Do not mention tools, agents, or internal process -- just the outcome and why."
)


def explain(llm: ClaimsLLM, tracker: UsageTracker, claim: dict, disposition: str, payout: int) -> str:
    """One-shot (non-tool) phrasing call, identical for the agent and the
    workflow, so the token/cost overhead of *deciding* the disposition is
    the only thing that differs between the two systems.
    """
    prompt = EXPLANATION_PROMPT.format(
        claim_id=claim["claim_id"],
        claim_type=claim["claim_type"],
        claimant=claim["claimant"],
        reported_amount=claim["reported_amount"],
        deductible=claim["deductible"],
        disposition=disposition,
        payout=payout,
    )
    response = llm.chat([{"role": "user", "content": prompt}])
    tracker.add(response.usage)
    return (response.choices[0].message.content or "").strip()
