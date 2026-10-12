# Cost per request — measured, then cut

Rates (`rag/llm.py`): **$0.15 / 1M input tokens, $0.75 / 1M output tokens** (`openai/gpt-oss-120b` on
Groq). Retrieval (Chroma) and rerank (local cross-encoder) have no per-call fee, so **cost is the
LLM call**. Every request logs `cost_usd` and `step_cost_usd` (`logs/queries.jsonl`).

## 1. Where the money goes (100 real logged requests)

| | Value |
|---|---|
| LLM calls (cache misses) | 80 |
| average input tokens / call | 575 (≈ $0.000086) |
| average output tokens / call | 183 (≈ $0.000137) |
| share of cost that is **output** | **61%** (this model spends output tokens on reasoning) |
| average cost / request, all 100 | $0.000178 |

Input is 76% of the tokens but only 39% of the bill. Cheapest saving = **not calling the model**.

## 2. The measured improvement

`python -m eval.cost_benchmark` replays 30 requests (10 handbook questions × as-written, lower-case
repeat, paraphrase) through the real pipeline, three ways. Real Groq calls, fresh cache per run
(`eval/cost_report.json`):

| Config | LLM calls | Cache hits | **$ / request** | vs A | Failures logged |
|---|---:|---:|---:|---:|---:|
| A — no cache (baseline) | 30 | 0 | **$0.000210** | — | 3 |
| B — semantic cache, old detector | 24 | 6 (20%) | **$0.000166** | −21% | 15 |
| C — semantic cache, fixed detector | 20 | 10 (33%) | **$0.000140** | **−33%** | 2 |

Two separate wins:

1. **Semantic cache (A→B, −21%).** Already in the app. A hit costs $0 and ~0–7 ms instead of an
   LLM call (about 1–5 s).
2. **Failure → test fix (B→C, a further −12 points).** The old detector flagged correct answers as
   failures and the cache refuses to store flagged answers, so those questions were re-billed
   every time. Fixing the detector ([SUPPORT_DRILL.md](SUPPORT_DRILL.md)) made them cacheable.
   False-alarm failure rows dropped 15 → 2 for the same traffic.

Caveats: 30 requests, one document, a traffic mix I chose (⅔ repeats/paraphrases). Real hit rate
depends on real repetition; the logged hit rate over all 100 real requests was 20%, so treat −33% as
the upper end for repetitive HR-style questions, not a forecast. Latency in the benchmark (p50 ≈ 5 s)
was slower than the logged p50 (≈ 0.9 s) because Groq was slower at that moment; it is not a result
of the change.

## 3. Money alarms already in place

`RAG_QUERY_COST_WARN_USD` (default 0.01) flags `expensive_query`; `saved_cost_usd` shows what each
hit avoided; `summarize()` / `GET /observability/summary` totals spend and savings.

## 4. Next levers (not done — no numbers claimed)

| Lever | Why it should help | Risk |
|---|---|---|
| Cheaper/smaller model for easy questions (refusals, single-fact lookups) | output tokens are 61% of cost | accuracy: needs the e2e + failure cases run on it first |
| Lower reasoning effort on the reasoning model | cuts output tokens directly | same |
| Fewer chunks (`rerank_top_k` 3 → 2) | trims ~575 input tokens | may drop the needed chunk; retrieval was not to be touched |
| Skip the LLM when there is no usable context (empty retrieval) | saves a call that can only produce a refusal | very rare in the logs |

Re-run `eval.cost_benchmark` and `eval.e2e_eval` after any of these and add the row to the table above.
