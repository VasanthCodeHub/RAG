"""Thin server-side wrappers around eval/judges.py + eval/run_regression.py,
so pages/1_Evaluation.py can call these over HTTP instead of importing
eval/* and rag/* in-process (which would double-load the embedding/
cross-encoder models the main API process already holds).
"""

import functools

from fastapi import APIRouter

from api.schemas import ApiKeyRequest
from eval.judges import LLMJudge, check_judge_calibration, rule_check
from eval.regression_cases import JUDGE_CALIBRATION_SET, REGRESSION_CASES, RESUME_CORPUS
from eval.run_regression import CROSS_ENCODER_MODEL, RERANK_TOP_K, combined_score, old_buggy_rerank
from rag.llm import GroqLLM
from rag.prompt import ANSWER_PROMPT
from rag.rerank import CrossEncoderRerank
from rag.retrieval import EmbeddingRetrieval

router = APIRouter(tags=["eval"])


@functools.lru_cache(maxsize=1)
def _eval_resources():
    retrieval = EmbeddingRetrieval(documents=RESUME_CORPUS)
    reranker = CrossEncoderRerank(model_name=CROSS_ENCODER_MODEL)
    return retrieval, reranker


@router.post("/eval/calibration")
def run_calibration(req: ApiKeyRequest):
    judge = LLMJudge(GroqLLM(api_key=req.groq_api_key))
    return check_judge_calibration(judge, JUDGE_CALIBRATION_SET)


@router.post("/eval/regression")
def run_regression(req: ApiKeyRequest):
    retrieval, reranker = _eval_resources()
    llm = GroqLLM(api_key=req.groq_api_key)
    judge = LLMJudge(llm)

    rows = []
    by_problem_type: dict[str, list[tuple[float, float]]] = {}
    for case in REGRESSION_CASES:
        docs, _ = retrieval.retrieve(case["question"], top_k=100)

        before_docs, _ = old_buggy_rerank(reranker, case["question"], docs, RERANK_TOP_K)
        before_answer = llm.generate(
            ANSWER_PROMPT.format(query=case["question"], context="\n".join(before_docs))
        )
        after_docs, _ = reranker.rerank(case["question"], docs, top_k=RERANK_TOP_K)
        after_answer = llm.generate(
            ANSWER_PROMPT.format(query=case["question"], context="\n".join(after_docs))
        )

        scores = {}
        for label, docs_used, answer in (
            ("before", before_docs, before_answer),
            ("after", after_docs, after_answer),
        ):
            rules = rule_check(case, answer, docs_used)
            judge_result = judge.score(case["question"], "\n".join(docs_used), answer)
            score = combined_score(rules, judge_result)
            scores[label] = score
            rows.append(
                {
                    "problem_type": case["problem_type"],
                    "question": case["question"],
                    "stage": label,
                    "docs_used": len(docs_used),
                    **rules,
                    "judge_helpfulness": judge_result["helpfulness"],
                    "judge_tone": judge_result["tone"],
                    "score": round(score, 2),
                    "answer": answer,
                }
            )
        by_problem_type.setdefault(case["problem_type"], []).append((scores["before"], scores["after"]))

    summary = []
    for problem_type, pairs in by_problem_type.items():
        before_avg = sum(p[0] for p in pairs) / len(pairs)
        after_avg = sum(p[1] for p in pairs) / len(pairs)
        summary.append(
            {
                "problem_type": problem_type,
                "before": round(before_avg, 2),
                "after": round(after_avg, 2),
                "delta": round(after_avg - before_avg, 2),
            }
        )

    return {"rows": rows, "summary": summary}
