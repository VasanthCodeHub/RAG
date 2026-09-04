"""
Regression + judging harness for the resume RAG pipeline.

What this does, in order (cheapest checks first):
1. Judge calibration: score a small hand-labeled set with the LLM judge and
   report agreement with our own grading, BEFORE trusting its scores below.
2. For each real failure in eval/trace_report.json (now pinned as a
   permanent case in eval/regression_cases.py), run the query through:
     - "before": the old CrossEncoderRerank logic (score > 0 filter that
       collapses to a single fallback document) -- reproduced here only for
       comparison, rag/rerank.py itself no longer contains it.
     - "after": the current (fixed) pipeline.
   Score both with cheap rule checks first (source present? correct
   refuse/answer behavior? expected fact present?), then the LLM judge for
   tone/helpfulness.
3. Print a before/after score per problem_type, so a regression shows up as
   a number going down, not just a vibe.

Run from the project root:
    .venv/Scripts/python.exe -m eval.run_regression
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

from eval.judges import LLMJudge, check_judge_calibration, rule_check
from eval.regression_cases import JUDGE_CALIBRATION_SET, REGRESSION_CASES, RESUME_CORPUS
from rag.llm import GroqLLM
from rag.prompt import ANSWER_PROMPT
from rag.rerank import CrossEncoderRerank
from rag.retrieval import EmbeddingRetrieval

load_dotenv()

RERANK_TOP_K = 3
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def old_buggy_rerank(model: CrossEncoderRerank, query: str, documents: list[str], top_k: int):
    """Reproduces the pre-fix `CrossEncoderRerank.rerank` behavior exactly,
    for a fair "before" comparison. Only keeps score > 0 documents, and
    if none clear that bar, falls back to the single best (still negative)
    match -- this is the bug fixed in rag/rerank.py.
    """
    cross_inp = [[query, passage] for passage in documents]
    cross_scores = model.model.predict(cross_inp)
    passage_scores = dict(enumerate(cross_scores))
    sorted_passages = sorted(passage_scores.items(), key=lambda x: x[1], reverse=True)
    relevants, scores = [], []
    for idx, score in sorted_passages[:top_k]:
        if score > 0:
            relevants.append(documents[idx])
            scores.append(score)
    if not relevants:
        idx, score = sorted_passages[0]
        relevants.append(documents[idx])
        scores.append(score)
    return relevants, scores


def run_case(retrieval, reranker, llm, case: dict) -> dict:
    docs, _ = retrieval.retrieve(case["question"], top_k=100)

    before_docs, _ = old_buggy_rerank(reranker, case["question"], docs, RERANK_TOP_K)
    before_answer = llm.generate(ANSWER_PROMPT.format(query=case["question"], context="\n".join(before_docs)))

    after_docs, _ = reranker.rerank(case["question"], docs, top_k=RERANK_TOP_K)
    after_answer = llm.generate(ANSWER_PROMPT.format(query=case["question"], context="\n".join(after_docs)))

    return {
        "before": {"docs": before_docs, "answer": before_answer},
        "after": {"docs": after_docs, "answer": after_answer},
    }


def combined_score(rules: dict, judge_result: dict) -> float:
    """Average of every pass/fail signal (rule checks + judge thresholds).
    A rule check a judge can't replace stays 0/1; judge dimensions pass at
    >= 3 out of 5.
    """
    signals = [
        rules["source_present"],
        rules["refusal_correct"],
        rules["keyword_present"],
        (judge_result["helpfulness"] or 0) >= 3,
        (judge_result["tone"] or 0) >= 3,
    ]
    return sum(signals) / len(signals)


def main():
    print("=== Step 1: judge calibration (do we trust the LLM judge?) ===\n")
    llm = GroqLLM()
    judge = LLMJudge(llm)
    calibration = check_judge_calibration(judge, JUDGE_CALIBRATION_SET)
    for row in calibration["rows"]:
        print(f"- {row['question']!r}")
        print(
            f"    human=(help={row['human_helpfulness']}, tone={row['human_tone']})  "
            f"judge=(help={row['judge']['helpfulness']}, tone={row['judge']['tone']})  "
            f"agree=(help={row['helpfulness_agree']}, tone={row['tone_agree']})"
        )
    print(
        f"\nJudge/human agreement (within 1 point): "
        f"helpfulness={calibration['helpfulness_agreement']:.0%}, "
        f"tone={calibration['tone_agreement']:.0%}  (n={calibration['n_cases']})\n"
    )
    if calibration["helpfulness_agreement"] < 0.75 or calibration["tone_agreement"] < 0.75:
        print(
            "WARNING: judge agreement is below 75% on the calibration set -- "
            "treat its scores on new cases below with caution.\n"
        )

    print("=== Step 2: before/after regression on real trace_report.json failures ===\n")
    retrieval = EmbeddingRetrieval(documents=RESUME_CORPUS)
    reranker = CrossEncoderRerank(model_name=CROSS_ENCODER_MODEL)

    by_problem_type: dict[str, list[float]] = {}
    for case in REGRESSION_CASES:
        result = run_case(retrieval, reranker, llm, case)
        by_problem_type.setdefault(case["problem_type"], [])

        row_scores = {}
        for label in ("before", "after"):
            answer = result[label]["answer"]
            docs = result[label]["docs"]
            rules = rule_check(case, answer, docs)
            judge_result = judge.score(case["question"], "\n".join(docs), answer)
            score = combined_score(rules, judge_result)
            row_scores[label] = score
            print(f"[{label:>6}] {case['question']!r} (trace_query_id={case['trace_query_id']})")
            print(f"          docs_used={len(docs)}  rules={rules}")
            print(f"          judge={judge_result}")
            print(f"          answer={answer[:160]!r}")
            print(f"          score={score:.2f}\n")

        by_problem_type[case["problem_type"]].append((row_scores["before"], row_scores["after"]))

    print("=== RESULT: score per problem type (before -> after) ===\n")
    print(f"{'problem_type':<22}{'before':>10}{'after':>10}{'delta':>10}")
    for problem_type, pairs in by_problem_type.items():
        before_avg = sum(p[0] for p in pairs) / len(pairs)
        after_avg = sum(p[1] for p in pairs) / len(pairs)
        print(f"{problem_type:<22}{before_avg:>10.2f}{after_avg:>10.2f}{after_avg - before_avg:>+10.2f}")


if __name__ == "__main__":
    main()
