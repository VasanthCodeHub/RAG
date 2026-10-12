# Support drill — from "it gave a wrong answer" to the one request

> Scenario (a drill, not a real customer ticket): *"Someone on the HR team said the app gave a wrong
> answer last week about getting a doctor's note for sick leave. They don't have an ID. It was
> around the 6th."*

No query_id, no exact time, no screenshot. This is what you can do with the log.
Tool: `eval/support_drill.py` (reads `logs/queries.jsonl`, `logs/app.jsonl`, `logs/failures.jsonl`).

## What every request logs

One row in `logs/queries.jsonl` per request (cache hits and errors included), and every line in
`logs/app.jsonl` carries the same `query_id` / `request_id` / `session_id`.

| Field | Why it is there |
|---|---|
| `query_id`, `request_id`, `session_id` | find one request; `request_id` is also the `x-request-id` response header; `session_id` comes from the `x-session-id` header or the `session_id` body field of `POST /query` |
| `ts` (UTC), `pdf_hash` | the "around the 6th" and "which document" part of a complaint |
| `query`, `answer` | read what the user saw instead of guessing |
| `model`, `prompt_version` | tie an answer to the model and prompt wording that produced it (`rag/prompt.py: PROMPT_VERSION`) |
| `chunks` | the passages sent to the model: `chunk_id` (hash of text), rerank `score`, text preview |
| `tool_calls` | tool name/args for agent rows (always `[]` for plain RAG, kept so rows share one shape) |
| `status`, `issues`, `alerts`, `error`, `error_type` | what the app itself thought of the request |
| `cache_lookup_ms`, `retrieve_ms`, `rerank_ms`, `generate_ms`, `total_ms` | where the time went |
| `prompt_tokens`, `completion_tokens`, `cost_usd`, `step_cost_usd`, `saved_cost_usd` | where the money went (only `generate` is billed) |

Rows written before this change (everything dated 2026-10-06) don't have `answer`, `model`,
`chunks` etc.; the tool says so instead of failing, and falls back to the answer stored in
`failures.jsonl` where there is one.

## The drill, step by step

**1. Narrow it.** Keywords from the complaint plus the day:

```
python -m eval.support_drill find --keyword "medical certificate" --since 2026-10-06 --until 2026-10-07
```

```
6 request(s) match
query_id  time (UTC)       status          ms         $  why suspect    question
831f3491  2026-10-06T08:57 issues_found   882   0.00022  low_relevance  When do I need a medical certificate for sick lea…
e4cd128a  2026-10-06T08:59 issues_found   960   0.00023  low_relevance  When do I need a medical certificate for sick lea…
1bacfd0a  2026-10-06T09:07 issues_found  1143   0.00021  low_relevance  When do I need a medical certificate for sick lea…
f94e75fe  2026-10-06T08:58 ok             948   0.00032  -              When is a medical certificate required for sick l…
b1c3fcb8  2026-10-06T09:00 ok               2   0.00000  -              When is a medical certificate required for sick l…
2278209a  2026-10-06T09:08 ok               2   0.00000  -              When is a medical certificate required for sick l…
```

Thousands of rows → 6. Suspects (flagged by the app) sort to the top. Other filters: `--session`,
`--status error`, `--min-cost`, `--slow-ms`.

**2. Open the top suspect.**

```
python -m eval.support_drill trace 831f3491
```

Prints the question, the answer, model, the chunks and their scores, per-step time and cost, every
log line for that request in order, and its failure record. For this one:

```
STATUS   issues_found  issues=['low_relevance']
  retrieve 11.1 ms | rerank 55.6 ms | generate 813.8 ms | total 881.6 ms | cost=$0.00022
LOG   WARNING stage=rerank status=low_relevance top_score=-0.8501 ...
LOG   INFO    stage=generate status=ok ... answer_len=202
FAILURE RECORD kinds=['issue:low_relevance'] status=open
```

**3. Decide what it was.** The answer stored in `failures.jsonl` for this request:

> *"A medical certificate is required when your sick-leave absence exceeds **three consecutive
> days**…"*

The handbook (`eval/fixtures/northwind_handbook.txt`, §3) says: *"A medical certificate is required
once an absence exceeds 3 consecutive days."* **The answer is correct.** The request was flagged
only because the cross-encoder scored its best chunk −0.85 (≤ 0).

So the finding is not "the model was wrong" — it is **a false alarm in our own detector.** The same
pattern in the whole log:

| | Count |
|---|---|
| failures logged for the handbook document | 35 |
| of those, the answer was a correct refusal or was supported by the context | **33** |
| real remaining flags | 2 (`3945def3`, `1bacfd0a`: answer adds claims the context doesn't state) |

A queue that is 94% false alarms hides the real ones, and every false alarm was also kept out of
the semantic cache (only "clean" answers are cached), so those questions paid for the LLM every
time ([COST.md](COST.md)).

**4. Fix it and pin it.** `observability/tracing.py: detect_issues` now treats a score ≤ 0 as a
failure only when the answer is *also* neither a refusal nor supported by the context
(`answer_is_grounded`: ≥ 60% of the answer's content words/numbers appear in the chunks, with
"three" = "3"). `eval/judges.py` learned the phrasings the log showed it missed ("does not
include", "isn't included", curly apostrophes). Empty retrieval/context/answer are flagged as before.

## The failure becomes a test

| Where | What it checks |
|---|---|
| `tests/test_failure_regression.py` | offline, no model: the exact sick-leave answer with score −0.8501 → **no** issue; the CEO refusal at −1.4316 → no issue; an unsupported answer at the same score → **still** `low_relevance`; empty answer/retrieval still flagged |
| `eval/failure_cases.jsonl` → `fc-831f3491` | promoted with `failure_loop.promote("831f3491", expected_keyword=[…])`; replayed against the real pipeline by `python -m eval.failure_loop` (needs `GROQ_API_KEY`) |

Proof it bites: with the old `detect_issues`, the sick-leave input returns `low_relevance` (the
test would fail); with the new one it returns nothing. Replay result: `2/2 passed`
(`fc-831f3491`, and `fc-80ec4acd`, whose label was wrong — see below).

While promoting, `fc-80ec4acd` ("Who is the CEO…?") had been saved as `should_answer: true`; the
handbook has no CEO, so the right behaviour is a refusal. It failed replay for that reason alone;
it is now `should_answer: false`.

## Limits (be honest in the demo)

- `answer_is_grounded` is word overlap, not understanding: a wrong answer made of words that appear
  in the context passes (e.g. the planted "100 days" injection sentence is *in* the document, so it
  counts as grounded — that attack is covered by the injection evals, not by this check).
- The top chunk for the sick-leave question (score −0.85) starts at the document title, so it looks
  like one large chunk covering the start of the handbook (only the preview was inspected; not
  investigated further). Retrieval was deliberately not touched; worth a look.
- The drill ran on the 2026-10-06 logs of this repo; the scenario/complaint is invented.
