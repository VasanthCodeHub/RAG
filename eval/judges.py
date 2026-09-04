"""
Judging utilities for scoring RAG answers.

Two tiers, cheapest first:
1. Rule-based checks (free, deterministic, no LLM call): is a source/context
   present? did the answer refuse when it shouldn't have (or vice versa)?
   does it contain the fact we expect?
2. An LLM judge, used only for what a rule can't decide -- tone and
   helpfulness. Its scores should not be trusted blindly: `check_judge_calibration`
   runs it against a small set of cases we've hand-scored ourselves and
   reports how often it agrees, so disagreement is visible before the judge
   is used to grade anything new.
"""

import json
import logging
import re

logger = logging.getLogger("rag.eval.judges")

# Phrases a "the context doesn't contain this" refusal tends to use. Kept
# broad on purpose -- a false positive here (calling a real answer a
# refusal) is cheap to notice by eye; missing a real refusal is not.
REFUSAL_PATTERNS = [
    "does not contain",
    "doesn't contain",
    "cannot determine",
    "can't determine",
    "cannot be determined",
    "don't know",
    "do not know",
    "no information",
    "not contain any information",
    "i'm not able to",
    "unable to determine",
    "not mentioned in the",
    "not provided in the",
]


# ---------------------------------------------------------------------------
# Tier 1: rule-based checks. Cheap, deterministic, run these first.
# ---------------------------------------------------------------------------


def has_source_context(contexts: list[str]) -> bool:
    """Did the pipeline actually pass any non-empty context to the LLM?"""
    return bool(contexts) and any(c.strip() for c in contexts)


def looks_like_refusal(answer: str) -> bool:
    """Does the answer read like an 'I don't know' / no-info refusal?"""
    lowered = (answer or "").lower()
    return any(p in lowered for p in REFUSAL_PATTERNS)


def refusal_matches_expectation(answer: str, should_answer: bool) -> bool:
    """True if the answer's refuse/don't-refuse behavior was correct.

    `should_answer=True` means the corpus actually contains the fact, so a
    refusal is wrong. `should_answer=False` means the fact genuinely isn't
    in the corpus, so a refusal is the *correct* behavior and an invented
    answer would be a hallucination.
    """
    refused = looks_like_refusal(answer)
    return refused != should_answer


def keyword_present(answer: str, keyword: str | list[str]) -> bool:
    """Literal fact-presence check, case-insensitive and whitespace-normalized
    so formatting differences alone don't register as a wrong answer.

    `keyword` can be a single required string, or a list of acceptable
    alternatives (any one matching counts as present) -- useful when more
    than one fact in the corpus would correctly answer the question.
    """

    def normalize(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").lower())

    keywords = [keyword] if isinstance(keyword, str) else keyword
    normalized_answer = normalize(answer)
    return any(normalize(k) in normalized_answer for k in keywords)


def rule_check(case: dict, answer: str, contexts: list[str]) -> dict:
    """Run every rule check that's free to run, for one (case, answer) pair.

    `case` needs: "should_answer" (bool) and "expected_keyword" (str).
    Returns a dict of individual pass/fail booleans plus an overall
    `rules_passed` (all of the above must pass).
    """
    source_ok = has_source_context(contexts)
    refusal_ok = refusal_matches_expectation(answer, case["should_answer"])
    keyword_ok = (
        keyword_present(answer, case["expected_keyword"])
        if case["should_answer"]
        else True  # no fact expected -> nothing to check for
    )
    return {
        "source_present": source_ok,
        "refusal_correct": refusal_ok,
        "keyword_present": keyword_ok,
        "rules_passed": source_ok and refusal_ok and keyword_ok,
    }


# ---------------------------------------------------------------------------
# Tier 2: LLM judge, for qualities rules can't check (tone, helpfulness).
# ---------------------------------------------------------------------------

JUDGE_RUBRIC = """You are grading one answer from a resume Q&A assistant. Be strict and consistent.

Question: {question}
Context given to the assistant: {context}
Assistant's answer: {answer}

Score the answer from 1 (worst) to 5 (best) on two dimensions:
- helpfulness: does it actually address the question using only the context, without padding?
- tone: is it direct and professional, neither evasive nor overconfident?

Respond with ONLY compact JSON, no prose, no markdown fences, in this exact shape:
{{"helpfulness": <1-5 integer>, "tone": <1-5 integer>, "reasoning": "<one short sentence>"}}
"""


def _strip_code_fence(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


class LLMJudge:
    """Wraps a `BaseLLM` to score answers on qualities a rule can't decide."""

    def __init__(self, llm):
        self.llm = llm

    def score(self, question: str, context: str, answer: str) -> dict:
        prompt = JUDGE_RUBRIC.format(question=question, context=context, answer=answer)
        raw = self.llm.generate(prompt)
        try:
            data = json.loads(_strip_code_fence(raw))
            return {
                "helpfulness": int(data["helpfulness"]),
                "tone": int(data["tone"]),
                "reasoning": data.get("reasoning", ""),
            }
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as error:
            logger.warning("llm_judge status=parse_error error=%r raw=%r", error, (raw or "")[:200])
            return {
                "helpfulness": None,
                "tone": None,
                "reasoning": f"unparseable judge output: {(raw or '')[:200]!r}",
            }


def check_judge_calibration(judge: LLMJudge, labeled_cases: list[dict], tolerance: int = 1) -> dict:
    """Score a small hand-labeled set with the LLM judge and report how often
    it agrees with our own grading (within `tolerance` points). Run this
    before trusting the judge's scores on any new, unlabeled case.

    Each case in `labeled_cases` needs: "question", "context", "answer",
    "human_helpfulness", "human_tone".
    """
    agree_help = 0
    agree_tone = 0
    rows = []
    for case in labeled_cases:
        result = judge.score(case["question"], case["context"], case["answer"])
        help_ok = (
            result["helpfulness"] is not None
            and abs(result["helpfulness"] - case["human_helpfulness"]) <= tolerance
        )
        tone_ok = (
            result["tone"] is not None
            and abs(result["tone"] - case["human_tone"]) <= tolerance
        )
        agree_help += int(help_ok)
        agree_tone += int(tone_ok)
        rows.append({**case, "judge": result, "helpfulness_agree": help_ok, "tone_agree": tone_ok})

    n = len(labeled_cases) or 1
    return {
        "helpfulness_agreement": agree_help / n,
        "tone_agreement": agree_tone / n,
        "n_cases": len(labeled_cases),
        "rows": rows,
    }
