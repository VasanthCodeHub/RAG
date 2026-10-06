# Weak spots & tough questions

## Known weak spots (we found them first)
| # | Weak spot | Impact | Mitigation / next step |
|---|---|---|---|
| 1 | **Small eval set** (10 e2e cases, one fixture doc) | 100% means "no failures seen", not "accurate" | grow to 50+ cases across several document types; track per-type |
| 2 | **Substring graders** are brittle (they gave us false failures) | wrong pass/fail either way | Unicode-normalised now; add LLM-judge audit on a sample |
| 3 | **No OCR** | scanned PDFs return 422 | add OCR step in `read_document_bytes` |
| 4 | **Tables/layout lost** in PDF text extraction | table questions answered badly | layout-aware parser |
| 5 | **Single-document scope**; one `pdf_hash` per question | no cross-document answers | multi-collection retrieval |
| 6 | **MCP subprocess per call** (~1 s) | agent/A2A latency | persistent MCP session |
| 7 | **Agent & A2A cost more, win rarely** on one index | 2.7× / ~4× latency | default to direct RAG; agents for multi-part questions |
| 8 | **No auth**, CORS `*`, GROQ key may be sent from the browser | local tool only | auth + server-side key only before any deployment |
| 9 | **Semantic cache can serve a near-miss** ("who is X"/"who is Y") | wrong answer served confidently | strict 0.92 threshold, clean-answers-only, per-document namespace, `DELETE /observability/cache` |
| 10 | **Prompt injection** defence is prompt + truncation, not a classifier | determined attacker may succeed | guard patterns, output validation, least-privilege tools (as in the claims agent) |
| 11 | **Single LLM provider** (Groq) | outage = app down | `BaseLLM` abstraction already allows a second provider |
| 12 | Cross-encoder + embedder are small English models | weak on other languages | multilingual models |

## Tough questions
**What does it cost?** ≈ 720 tokens ≈ **$0.0002 per question** with `gpt-oss-120b` ($0.15/$0.75 per M
tokens). 1,000 questions ≈ $0.21. A cache hit costs $0. Agent ≈ same tokens but 3× latency; the A2A
team ≈ 3× cost. Every query's cost is logged (`logs/queries.jsonl`) and alertable (`RAG_QUERY_COST_WARN_USD`).

**How accurate is it?** On our 10-case labelled set: 100% (RAG), 100% (agent), 100% (A2A subset) — on a
small, easy, single-document set, so read it as "no regressions", not a population estimate. On
unanswerable questions it refused 2/2; on the planted injection it was not hijacked 2/2.

**What happens when it's wrong?** Five layers: (1) the quality badge/`low_relevance` issue flags weak
retrieval; (2) the prompt tells the model to say when context lacks the answer; (3) wrong or flagged answers
go to the failure log (also on human rating ≤ 2); (4) one click promotes a failure into a permanent
regression case; (5) the sources are shown next to every answer so a human can verify.

**Can it leak data / be hijacked by the document?** Documents are untrusted input. Agent tool output is
capped and framed as data; claims-agent guards cut injected notes and enforce the required tool order in
code (attack success 100% → 0%). Not bullet-proof — see #10.

**Why not just use the agent for everything?** We raced them: on a known path a workflow beat the agent
(100% vs 60% pass, 4× cheaper) — see [week 7](week7_claims_submission.md). So the default is plain RAG.

**Why is retrieval dense-only when you built hybrid?** Hybrid (BM25+vector) helps rare exact terms and
is in `rag/retrieval.py`, but the dense+cross-encoder pipeline performed well in production and was
deliberately left untouched during the merge. It is the first thing to switch on if keyword-heavy
documents underperform.
