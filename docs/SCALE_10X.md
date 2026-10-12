# 10x traffic — what breaks first, and the plan

## Assumption (stated, not measured)

The logs are single-developer traffic (≈100 requests). I assume **today ≈ 1,000 requests/day** and
plan for **10,000/day**: about 7/min on average, **≈ 70/min at a 10× peak** (≈ 1.2/sec). Change the
numbers and re-run the probes below; the *order* of what breaks is the useful part.

## What I measured

Scripts: `eval/load_probe.py` (real concurrent requests, one process, cache off) and synthetic log
files built from real rows.

### A. Concurrency on one process (real Groq calls)

| Concurrent requests | Throughput | p50 | p95 | avg rerank | avg generate | Errors |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.07 req/s | 0.9 s | 0.9 s | 204 ms | 692 ms | 0 |
| 4 | 2.22 | 1.8 s | 1.8 s | 784 ms | 836 ms | 0 |
| 8 | 0.84 | 3.2 s | 6.5 s | 1,470 ms | 2,717 ms | 0 |
| 16 | 0.20 | 17.5 s | 29.5 s | 2,892 ms | 15,601 ms | **9 of 16** |

Two things break: the local **reranker slows 14×** under contention (204 ms → 2.9 s, CPU-bound,
shared by all threads) and the **LLM provider rate-limits**: the errors are Groq
`429 Rate limit reached … tokens per minute` (`on_demand` tier). `GroqLLM` retries 3× with no
back-off, so a burst turns into more load and then into hard failures. A rerun of the 16-wide burst
showed 2 errors instead of 9, because the limit depends on the minute's usage — it is a cliff,
not a smooth curve.

### B. Logging itself (synthetic files built from real rows)

| Operation | 100 requests | 1,000 | 10,000 | 100,000 |
|---|---:|---:|---:|---:|
| `trace_report.json` append (read + rewrite whole file, per request) | 26 ms (0.5 MB) | 130 ms (4.7 MB) | **1,076 ms (46.7 MB)** | — |
| dashboard `summarize()` (re-read all of `queries.jsonl`) | — | 16 ms | 88 ms | **2,066 ms (65 MB)** |
| `failures.jsonl` rewrite (per failure, under a lock) | — | 153 ms | 362 ms | — |

`record_query_trace` (observability/tracing.py) reads and rewrites the entire JSON file on **every
request**, with **no lock**. At 10,000 queries it adds ~1 s of CPU/disk to each request, and two
concurrent requests can read the same file and overwrite each other's entry (lost traces). It is
already 0.5 MB / 114 queries today.

## What breaks first (in order)

1. **LLM rate limit (429)** — the first hard failure, at ≈ 8–16 simultaneous requests on this tier.
2. **Reranker CPU** — latency grows with concurrency before errors start.
3. **`trace_report.json` rewrite** — slows every request and loses traces under concurrency.
4. **Dashboard / `find_query` re-reading whole JSONL files** — fine to ~10k rows, seconds at 100k.
5. **Single process state** — the semantic cache and the loaded-document store are in-process memory;
   a second worker would have its own cold cache (hit rate drops) and not know uploaded documents
   until rehydrated from Chroma.

## Plan

| # | Change | Fixes | Done? |
|---|---|---|---|
| 1 | Stop writing `eval/trace_report.json` per request in production (`RAG_TRACE_FILE=""`), keep `queries.jsonl` as the record; it already holds answer, chunks and timings | #3, 4× less disk I/O | config only, **not applied** |
| 2 | Retry with exponential back-off + jitter on 429 and honour `retry-after`; cap in-flight LLM calls with a semaphore (≈ the tier's tokens/min ÷ 750 tokens per call) | #1 | not done |
| 3 | Queue excess requests and answer `429`/`503 Retry-After` to the client instead of failing after 3 instant retries; alert when `error_type=RateLimitError` rises | #1 | not done (error_type is already logged) |
| 4 | Bound reranker work: run it in a limited worker pool (≈ CPU cores) so requests wait in line instead of all slowing together | #2 | not done |
| 5 | Raise cache hit rate: it is the only lever that cuts load *and* cost ([COST.md](COST.md): −33% cost on repetitive traffic). Share it across workers (Redis or similar) | #1, #2, #5 | in-process version exists |
| 6 | Move per-request rows from JSONL to a database (SQLite → Postgres) with indexes on `ts`, `session_id`, `query_id`; keep `app.jsonl` for lines. `support_drill.find` becomes a query | #4 | not done |
| 7 | Run N workers behind a load balancer only after 2, 3 and 5; otherwise more workers just hit the rate limit sooner | #5 | — |

## Cost at 10×

Using $/request from [COST.md](COST.md): 10,000/day × $0.000210 = **$2.10/day** with no cache;
× $0.000140 = **$1.40/day** with the cache on repetitive traffic. The bill is not the problem at
this size; the rate limit and latency are.

## What to watch (so it is not discovered by customers)

`p95 total_ms` and `rerank_ms` from `/observability/summary`; count of `error_type=RateLimitError`;
`cache_hit_rate`; size of `logs/` and `eval/trace_report.json`.

## Not covered

No load test beyond 16 concurrent requests from one machine; the Groq tier's exact limit was not
looked up; the React front-end, MCP and A2A paths were not load-tested.
