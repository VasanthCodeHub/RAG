# Observability (`observability/`)

Goal: for any answer, say what happened, how long, how much it cost, and — when it went wrong —
turn that into a permanent test.

## Files

- `observability/tracing.py` — `configure_logging`, `traced_stage` (times each stage and logs
  `stage=… status=… duration_ms=…`), `detect_issues`, `record_query_trace` (writes
  `eval/trace_report.json`).
- `observability/metrics.py` — JSON log formatter, `query_id`/`request_id` context vars,
  per-query metrics, failure log, alerts, `summarize()`.

## What is recorded (under `logs/`, git-ignored)

| File | Content |
|---|---|
| `app.jsonl` | every log line as JSON, stamped with `query_id` and `request_id` — filter one id to see one question's whole journey |
| `queries.jsonl` | one row per request: `query_id`/`request_id`/`session_id`, question **and answer**, `model`, `prompt_version`, the `chunks` sent (id, score, preview), `tool_calls`, per-step ms and cost, tokens, cache hit/miss, issues, `error_type` — full field list in [SUPPORT_DRILL.md](SUPPORT_DRILL.md) |
| `failures.jsonl` | queries that went wrong: detected issues, exceptions, or a human rating ≤ 2 |

Every HTTP response carries `x-request-id`. Cost uses the model's published per-token rates
(`rag/llm.py`: $0.15 / $0.75 per million prompt / completion tokens).

## Issue detection (`detect_issues`)

`empty_retrieval`, `low_relevance` (top rerank score ≤ 0 **and** the answer is neither a refusal nor
supported by the retrieved chunks — a low score alone was a false alarm for 33 of 35 logged handbook
failures), `empty_context`, `empty_answer`. These
set `status="issues_found"` and write a failure row. Alerts fire on queries slower than
`RAG_SLOW_QUERY_MS` or costlier than `RAG_QUERY_COST_WARN_USD`.

## Dashboard (UI → Observability, API → `/observability/*`)

`/summary` (volume, cache hit rate, spend, saved by cache, p50/p95, per-stage averages, errors),
`/queries`, `/failures`, `/cases`, `/cache` (GET stats, DELETE clear),
`POST /failures/{id}/promote` → adds a regression case.

## The failure → test loop

1. a query is flagged (auto issue, exception, or low human rating)
2. you open it in the Failures tab and **promote** it (expected keyword / should-answer)
3. `eval/failure_loop.py` appends it to `failure_cases.jsonl`; the regression suite now covers it forever

## Semantic cache, measured

On this machine's 54 logged queries: cache hit ≈ **4 ms** vs miss ≈ **1185 ms**; hit-rate 17%;
$0.0094 spent, $0.0021 saved. The p95 is dominated by cold model loads and the LLM call.

## Week 11 deliverables

- Find one bad request from a vague complaint: `python -m eval.support_drill` → [SUPPORT_DRILL.md](SUPPORT_DRILL.md)
- Failure turned into a test: `tests/test_failure_regression.py`, `eval/failure_cases.jsonl`
- Cost per request, measured before/after: `python -m eval.cost_benchmark` → [COST.md](COST.md)
- 10x traffic: `python -m eval.load_probe` → [SCALE_10X.md](SCALE_10X.md)

See also: [TRACING.md](TRACING.md) (original design notes) and [TRACE_FINDINGS.md](TRACE_FINDINGS.md).
