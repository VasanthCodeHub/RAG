"""Failure -> regression-test loop.

1. Failures are logged automatically (rag/observability.record_failure):
   detected pipeline issues, exceptions, and low human ratings.
2. `promote()` turns one logged failure into a permanent case in
   eval/failure_cases.jsonl. A human supplies what a correct answer must
   contain (`expected_keyword`) or says it should be refused -- the log can
   tell us *that* it failed, not what right looks like.
3. `replay()` re-runs every case through the real pipeline (cache bypassed)
   and applies the same rule checks as eval/judges.py. Run it from the CLI
   (`python -m eval.failure_loop`) or via tests/test_observability.py.

Cases are pinned to a `pdf_hash`, so replay re-opens that document's
persisted Chroma collection (.chroma_data) -- no re-upload needed.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from observability import metrics as observability

CASES_FILE = Path(os.getenv("RAG_FAILURE_CASES_FILE", "eval/failure_cases.jsonl"))
CHROMA_PERSIST_DIR = ".chroma_data"
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def load_cases() -> list[dict]:
    if not CASES_FILE.exists():
        return []
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def promote(
    query_id: str,
    *,
    should_answer: bool = True,
    expected_keyword: str | list[str] | None = None,
    problem_type: str | None = None,
) -> dict:
    """Pin a logged failure as a permanent regression case (idempotent per
    question+document). Raises KeyError for an unknown id, ValueError if the
    failure has no question/document to replay against.
    """
    failure = observability.get_failure(query_id)
    if failure is None:
        raise KeyError(query_id)
    if not failure.get("query") or not failure.get("pdf_hash"):
        raise ValueError("Failure has no query/pdf_hash recorded, so it can't be replayed.")

    cases = load_cases()
    existing = next(
        (c for c in cases if c["question"] == failure["query"] and c["pdf_hash"] == failure["pdf_hash"]),
        None,
    )
    if existing:
        observability.mark_failure_promoted(query_id, existing["case_id"])
        return existing

    case = {
        "case_id": f"fc-{query_id}",
        "trace_query_id": query_id,
        "created": datetime.now(timezone.utc).isoformat(),
        "question": failure["query"],
        "pdf_hash": failure["pdf_hash"],
        "problem_type": problem_type or failure["kinds"][0].split(":")[-1],
        "should_answer": should_answer,
        "expected_keyword": expected_keyword or "",
        "original_answer": failure.get("answer"),
        "failure_kinds": failure["kinds"],
    }
    CASES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CASES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(case, ensure_ascii=False) + "\n")
    observability.mark_failure_promoted(query_id, case["case_id"])
    return case


def evaluate_case(case: dict, answer: str, contexts: list[str], issues: list[dict]) -> dict:
    """Pure check of one replayed answer (no model calls -- unit-testable)."""
    from eval.judges import rule_check

    rules = rule_check(case, answer, contexts)
    # A should-refuse case legitimately trips low_relevance, so only demand a
    # clean pipeline run when an answer is expected.
    no_issues = not issues if case["should_answer"] else True
    return {**rules, "no_pipeline_issues": no_issues, "passed": rules["rules_passed"] and no_issues}


def build_pipeline(pdf_hash: str, api_key: str | None = None):
    from rag.llm import GroqLLM
    from rag.pipeline import SimpleRAGPipeline
    from rag.rerank import CrossEncoderRerank
    from rag.retrieval import ChromaRetrieval

    retrieval = ChromaRetrieval(collection_name=f"doc-{pdf_hash}", persist_dir=CHROMA_PERSIST_DIR)
    if retrieval.collection.count() == 0:
        raise RuntimeError(f"No ingested document for pdf_hash={pdf_hash}; re-upload the PDF once.")
    return SimpleRAGPipeline(
        retrieval=retrieval,
        llm=GroqLLM(api_key=api_key),
        rerank=CrossEncoderRerank(model_name=CROSS_ENCODER_MODEL),
        pdf_hash=pdf_hash,
    )


def replay(cases: list[dict] | None = None, api_key: str | None = None) -> list[dict]:
    cases = load_cases() if cases is None else cases
    pipelines: dict[str, object] = {}
    results = []
    for case in cases:
        try:
            if case["pdf_hash"] not in pipelines:
                pipelines[case["pdf_hash"]] = build_pipeline(case["pdf_hash"], api_key)
            response = pipelines[case["pdf_hash"]].run(case["question"], use_cache=False)
            verdict = evaluate_case(case, response.answer, response.contexts, response.issues)
            results.append({"case": case, "answer": response.answer, **verdict})
        except Exception as error:  # a case that can't run is a failing case, not a skipped one
            results.append({"case": case, "answer": None, "passed": False, "error": repr(error)})
    return results


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv

    load_dotenv()
    cases = load_cases()
    if not cases:
        print(f"No cases in {CASES_FILE}. Promote a failure from the Observability page first.")
        return 0
    results = replay(cases)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['case']['case_id']} ({r['case']['problem_type']}) {r['case']['question']!r}")
        if not r["passed"]:
            print(f"        {r.get('error') or {k: v for k, v in r.items() if k not in ('case', 'answer')}}")
    failed = sum(1 for r in results if not r["passed"])
    print(f"\n{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
