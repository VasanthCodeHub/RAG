"""Measure cost per request with real Groq calls, and what each saving costs.

Replays one fixed traffic mix through the real pipeline (handbook fixture,
real retrieval + rerank + LLM) three ways:

  A  no cache             every request pays for an LLM call   (baseline)
  B  cache, old detector  low-rerank-score answers are never cached
  C  cache, new detector  grounded / refusal answers ARE cached (current code)

Traffic = 10 questions asked 3 times each: as written, as a lower-case repeat
(what users really do), and as a paraphrase -- 30 requests per run.

    .venv/Scripts/python.exe -m eval.cost_benchmark

Needs GROQ_API_KEY and the handbook already uploaded once (its Chroma
collection is reused). Writes eval/cost_report.json; narrative and numbers in
docs/COST.md. Uses its own temp log dir and cache, so the real logs/ are untouched.
"""

import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
os.environ["RAG_TRACE_FILE"] = ""  # never append bench queries to eval/trace_report.json

from eval.e2e_eval import CASES  # noqa: E402  (after env setup)

OUT = Path(__file__).parent / "cost_report.json"
HANDBOOK_HASH = "fbb869c91f087b94da16d8c7cd777284"  # same document the logged failures used

PARAPHRASES = {
    "leave-days": "what's the annual leave allowance for a full time employee",
    "carryover": "can leftover vacation days roll into next year and for how long",
    "sick-cert": "after how many sick days is a doctor's note needed",
    "parental": "how many weeks of parental leave does the second parent get",
    "flight-class": "which cabin class is allowed on an eight hour flight",
    "notice-mgr": "how much notice must a manager give when leaving",
    "multi-hop": "what is the learning budget and what is the daily travel meal allowance",
    "unanswerable-ceo": "who runs Northwind Logistics as chief executive",
    "unanswerable-stock": "what did Northwind shares trade at last quarter",
    "injection": "how many days of annual leave does an employee get per the handbook",
}


def traffic() -> list[str]:
    asks = [c["q"] for c in CASES]
    asks += [c["q"].lower().rstrip("?") for c in CASES]
    asks += [PARAPHRASES[c["id"]] for c in CASES]
    return asks


def legacy_detect_issues(retrieved, reranked, scores, answer):
    """Pre-fix behaviour: any top rerank score <= 0 is a low_relevance failure."""
    from observability import tracing

    issues, top = tracing.detect_issues(retrieved, reranked, scores, answer)
    if top is not None and top <= 0 and not any(i["type"] == "low_relevance" for i in issues):
        issues.append({"stage": "rerank", "type": "low_relevance", "detail": "score <= 0 (legacy)"})
    return issues, top


def run_config(name, pipeline, cache, detector, asks):
    from observability import metrics
    from rag import pipeline as pipeline_module

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["RAG_LOG_DIR"] = tmp
        pipeline.cache = cache
        pipeline_module.detect_issues = detector
        for q in asks:
            pipeline.run(q, use_cache=cache is not None)
        rows = metrics._read(metrics.queries_path())
        failures = metrics.list_failures()
    hits = [r for r in rows if r["cache_hit"]]
    total_cost = sum(r["cost_usd"] for r in rows)
    lat = [r["total_ms"] for r in rows]
    return {
        "config": name,
        "requests": len(rows),
        "llm_calls": len(rows) - len(hits),
        "cache_hits": len(hits),
        "hit_rate": round(len(hits) / len(rows), 3),
        "total_cost_usd": round(total_cost, 6),
        "cost_per_request_usd": round(total_cost / len(rows), 7),
        "avg_tokens_per_llm_call": round(
            statistics.fmean([r["prompt_tokens"] + r["completion_tokens"] for r in rows if not r["cache_hit"]]), 1
        ),
        "p50_ms": round(statistics.median(lat), 1),
        "p95_ms": round(sorted(lat)[int(0.95 * (len(lat) - 1))], 1),
        "failures_logged": len(failures),
        "avg_ms_cache_hit": round(statistics.fmean([r["total_ms"] for r in hits]), 1) if hits else None,
    }


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from eval.failure_loop import build_pipeline
    from observability import tracing
    from rag.semantic_cache import SemanticCache

    pipe = build_pipeline(HANDBOOK_HASH)
    asks = traffic()
    pipe.run("warm up the models", use_cache=False)  # keep model load time out of the numbers

    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, use_cache, detector in (
            ("A no cache", False, tracing.detect_issues),
            ("B cache + old detector", True, legacy_detect_issues),
            ("C cache + new detector", True, tracing.detect_issues),
        ):
            cache = SemanticCache(path=Path(tmp) / f"{name[0]}.jsonl") if use_cache else None
            started = time.time()
            res = run_config(name, pipe, cache, detector, asks)
            res["wall_s"] = round(time.time() - started, 1)
            results.append(res)
            print(json.dumps(res))
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    base = results[0]["cost_per_request_usd"]
    print(f"\n{'config':<26}{'$/request':>12}{'vs A':>8}{'hit%':>7}{'p50 ms':>9}{'failures':>10}")
    for r in results:
        print(
            f"{r['config']:<26}{r['cost_per_request_usd']:>12.6f}{r['cost_per_request_usd'] / base - 1:>+8.0%}"
            f"{r['hit_rate']:>7.0%}{r['p50_ms']:>9.0f}{r['failures_logged']:>10}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
