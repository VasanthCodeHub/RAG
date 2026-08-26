# Tracing & Debugging Log

This documents the tracing work added to the RAG pipeline, and a real issue
it surfaced during local testing.

## What was added

Structured, per-query logging across the pipeline stages (`rag/tracing.py`,
wired into `rag/pipeline.py`, `rag/llm.py`, `rag/retrieval.py`):

- Every call to `SimpleRAGPipeline.run()` gets a short `query_id` so all log
  lines for one question can be grepped together.
- Each stage (`retrieve`, `rerank`, `generate`) logs status, duration, and
  stage-specific counters (docs retrieved, docs after rerank, top rerank
  score, answer length).
- LLM calls (`GroqLLM`, `GeminiLLM`) log every retry attempt and the final
  error if all retries are exhausted.
- Embedding/BM25 index build time is logged on ingest.
- Configurable via `RAG_LOG_LEVEL` (default `INFO`) and `RAG_LOG_FILE`
  (optional, writes to a file in addition to the console).

See [`rag/tracing.py`](rag/tracing.py) for the implementation.

## Proof: logs from a local test run

App was run locally with `streamlit run app.py`, a PDF uploaded, and two
questions asked. Raw log output:

```
2026-08-26 13:08:57 [INFO] rag.pipeline: query_id=7dba39a1 stage=start query='gimme all the projects name he worked'
2026-08-26 13:08:57 [INFO] rag.pipeline: stage=retrieve status=ok duration_ms=60.8 query_id='7dba39a1' docs_retrieved=21
2026-08-26 13:08:59 [INFO] rag.pipeline: stage=rerank status=ok duration_ms=1526.4 query_id='7dba39a1' docs_after_rerank=1 top_score=-6.2295
2026-08-26 13:09:00 [INFO] rag.pipeline: stage=generate status=ok duration_ms=812.6 query_id='7dba39a1' answer_len=73
2026-08-26 13:09:00 [INFO] rag.pipeline: query_id=7dba39a1 stage=complete status=ok total_duration_ms=2401.6

2026-08-26 13:09:17 [INFO] rag.pipeline: query_id=b5929a12 stage=start query=' Quadrix AI?'
2026-08-26 13:09:17 [INFO] rag.pipeline: stage=retrieve status=ok duration_ms=34.5 query_id='b5929a12' docs_retrieved=21
2026-08-26 13:09:18 [INFO] rag.pipeline: stage=rerank status=ok duration_ms=1259.0 query_id='b5929a12' docs_after_rerank=2 top_score=7.3396
2026-08-26 13:09:19 [INFO] rag.pipeline: stage=generate status=ok duration_ms=1331.8 query_id='b5929a12' answer_len=1467
2026-08-26 13:09:19 [INFO] rag.pipeline: query_id=b5929a12 stage=complete status=ok total_duration_ms=2626.4
```

## Issue found

Comparing the two queries side by side:

| query_id | docs retrieved | docs after rerank | top rerank score | answer length |
|---|---|---|---|---|
| `7dba39a1` | 21 | 1 | **-6.2295** | 73 chars |
| `b5929a12` | 21 | 2 | 7.3396 | 1467 chars |

`7dba39a1` ("gimme all the projects name he worked") reranked to a single
document with a **negative** cross-encoder score, and the pipeline still
generated an answer from it as if the context were relevant.

Root cause, in [`rag/rerank.py`](rag/rerank.py) (`CrossEncoderRerank.rerank`):
it only keeps documents with `score > 0`; if none clear that bar, it falls
back to returning the single best-scoring document anyway — even when that
score is negative, meaning the cross-encoder judged it *irrelevant*. Before
tracing was added, this failure mode was invisible: the pipeline returned an
answer with no error, so there was nothing to notice short of manually
reading the (possibly wrong) answer.

## Fix applied

`SimpleRAGPipeline.run()` (`rag/pipeline.py`) now explicitly logs a
`WARNING` when the top rerank score is `<= 0`:

```
2026-08-26 13:13:18 [WARNING] rag.pipeline: query_id=001a417f stage=rerank status=low_relevance top_score=-11.3656 reason=no_document_cleared_positive_score
```

This makes low-relevance-context answers greppable/alertable
(`grep "status=low_relevance"`) instead of silently blending into normal
`status=ok` output. It does not change the answer behavior (fallback logic
in `CrossEncoderRerank` is unchanged) — it only makes the existing failure
mode observable.

## Possible follow-ups (not yet done)

- Surface the `low_relevance` warning in the Streamlit UI (e.g. a caption
  under the answer) instead of only in server logs.
- Consider whether `CrossEncoderRerank` should return no context (and let
  the pipeline short-circuit with "I don't know") instead of the best
  negative-scored document, for queries clearly outside the document's
  scope.
