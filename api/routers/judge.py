from fastapi import APIRouter

from api.schemas import JudgeRequest, JudgeResponse
from eval.judges import LLMJudge, has_source_context
from rag.llm import GroqLLM

router = APIRouter(tags=["judge"])


@router.post("/judge", response_model=JudgeResponse)
def judge_answer(req: JudgeRequest):
    llm = GroqLLM(api_key=req.groq_api_key)
    judge = LLMJudge(llm)
    judge_result = judge.score(req.question, "\n".join(req.contexts), req.answer)

    # A live chat question has no known `should_answer`/`expected_keyword`
    # label the way a pinned regression case does, so only the one rule
    # check that needs no label -- is there any source context at all -- is
    # meaningful here. The rest are surfaced as null rather than guessed.
    rules = {
        "source_present": has_source_context(req.contexts),
        "refusal_correct": None,
        "keyword_present": None,
        "rules_passed": None,
        "note": (
            "refusal_correct/keyword_present need a known should_answer/"
            "expected_keyword label, which a live chat question doesn't have."
        ),
    }
    return JudgeResponse(rules=rules, judge=judge_result)
