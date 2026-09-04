# Trace Report Findings & Fixes

Source: [`eval/trace_report.json`](eval/trace_report.json) — 3 real queries run
through the app, all flagged `status: "issues_found"`.

| query_id | query | docs_retrieved | docs_after_rerank | top_score | issue |
|---|---|---|---|---|---|
| `bb1743ba` | "what are the project's this candidate worked?" | 25 | 1 | -8.3577 | low_relevance |
| `73d12427` | "who is the candidate for this resume?" | 25 | 1 | -9.3903 | low_relevance |
| `e8990bdf` | "which technology this project by the way" | 25 | 1 | -0.4726 | low_relevance |

All three queries hit the same `rerank`-stage issue, and one of them
(`73d12427`) produced a visibly wrong answer: *"The provided context does not
contain any information about a specific résumé..."* — even though the
retrieved set of 25 chunks included one starting with `"Midhun T Mobile
Developer SUMMARY..."`.

## Issue 1 — reranker collapsed to 1 document regardless of `rerank_top_k`

**Root cause** (`rag/rerank.py`, `CrossEncoderRerank.rerank`): the method
only kept documents with a cross-encoder `score > 0`. When *none* of the
`top_k` candidates cleared that bar (all three logged queries), it fell back
to returning just the single highest-scoring document — even though that
score was still negative (i.e. the model judged it irrelevant too).

This was already known and logged (see `TRACING.md`'s "Possible follow-ups"
section) but never actually fixed — only a `WARNING` log line was added.

**Impact:** `rerank_top_k` defaults to 3, but every low-confidence query
collapsed the pipeline's context down to exactly 1 chunk, discarding the
other 2 slots even when they held genuinely useful information. For
`73d12427`, the one chunk that survived (a job-platform product description)
happened to *not* contain the candidate's name, while a chunk that did
(`"Midhun T Mobile Developer..."`) was discarded purely because it wasn't
the single top-scoring match — producing a confident "I don't know" instead
of the right answer.

**Fix:** `CrossEncoderRerank.rerank` now always returns the top `top_k`
documents sorted by score, with no positive-score filter. Low relevance is
still detected and surfaced (see `detect_issues` / the `status=low_relevance`
warning in `rag/pipeline.py`), but the pipeline no longer throws away
otherwise-retrieved context just because the reranker wasn't confident about
its single best pick.

## Issue 2 — PDF-extracted text has collapsed context density from repeated spaces

**Root cause** (`rag/data_helper.py` → `rag/text_utils.py`): `pypdf`'s
`extract_text()` reproduces justified-text layout with runs of 2-3 spaces
between words (visible directly in the trace previews, e.g. `"Project  Name:
Swapsi   Technologies:  React  Native"`). This text is chunked as-is with a
1000-character `chunk_size`, so a meaningful fraction of every chunk's
character budget is wasted on redundant whitespace instead of content —
shrinking how much actual resume text fits per chunk and increasing the odds
that a fact and its context land in different chunks.

**Fix:** added `clean_text()` in `rag/text_utils.py`, which collapses runs of
spaces/tabs (leaving newlines untouched so the splitter's paragraph/line
boundaries still work) before chunking. `text2chunk()` now calls it
automatically, so both `app.py` and `main.py` get the benefit with no call-site
changes.

## Verification

Both fixes were exercised directly (no PDF/model download required for the
rerank fix, since it's pure sorting logic):

```
>>> clean_text("Project  Name:  Swapsi   Technologies:  React  Native, Expo")
'Project Name: Swapsi Technologies: React Native, Expo'

>>> # rerank fallback: top_k=3, no score clears 0
>>> cross_scores = [-5.0, 2.0, -1.0, 0.5, -9.0]
>>> # before: relevants=['b'], scores=[2.0]           (collapsed to 1)
>>> # after:  relevants=['b', 'd', 'c'], scores=[2.0, 0.5, -1.0]  (full top_k)
```

## Not changed

- The `score <= 0` → `low_relevance` warning/issue detection in
  `rag/pipeline.py` and `rag/tracing.py` is intentionally left as-is — it's
  correct observability, separate from the context-selection bug above.
- No change to which embedding/cross-encoder models are used. The underlying
  retrieval quality for very short/ambiguous queries (e.g. "who is the
  candidate for this resume?") is still limited by those general-purpose
  models on a resume-domain, unusually-formatted corpus; that's a model/data
  choice, not a bug.
