# RAG (`rag/`)

Retrieval-augmented generation over a single uploaded document. This part is the
most-tested piece of the app and was **not modified** during the merge.

## Pipeline

```
upload ─► read ─► clean ─► chunk ─► embed ─► Chroma (persistent)
ask ─► [semantic cache] ─► dense retrieve top-100 ─► cross-encoder rerank top-3 ─► LLM ─► answer
```

| Stage | What we use | File |
|---|---|---|
| **Reading** | By extension: `pypdf` for PDF (existing `PDFReader`), stdlib zip+XML for DOCX, tag-stripping for HTML, UTF-8 for text-like files | `rag/data_helper.py` |
| **Cleaning** | Collapse runs of spaces/tabs (pypdf leaves `"Project  Name:  X"` on justified text); newlines kept so the splitter's separators still work | `rag/text_utils.py::clean_text` |
| **Chunking** | LangChain `RecursiveCharacterTextSplitter`, **1000 characters, 200 overlap**. It splits on paragraph → line → word boundaries, so chunks rarely cut mid-sentence | `rag/text_utils.py::text2chunk` |
| **Embedding** | `sentence-transformers` `all-MiniLM-L6-v2`, L2-normalised (dot product = cosine) | `rag/retrieval.py` |
| **Vector store** | Chroma `PersistentClient` in `.chroma_data/`, one collection per document: `doc-<sha256[:32] of file bytes>`. Re-uploading identical bytes skips embedding | `ChromaRetrieval` |
| **Retrieval** | **Dense vector search, top-100** (`retrieval_top_k=100`; for small docs this is every chunk) | `ChromaRetrieval.retrieve` |
| **Reranking** | Cross-encoder `cross-encoder/ms-marco-MiniLM-L-6-v2` scores each (query, chunk) pair; keep **top-3** sorted by score. No positive-score filter (see below) | `rag/rerank.py` |
| **Generation** | Groq `openai/gpt-oss-120b`, temperature 0, `reasoning_format=parsed`; prompt = query + the 3 chunks | `rag/llm.py`, `rag/prompt.py` |
| **Semantic cache** | Exact normalised-text match, then embedding cosine ≥ **0.92**, keyed by `(document, model)`; TTL 7 d, 500 entries, JSONL persisted. Only clean answers are cached | `rag/semantic_cache.py` |

Also in the repo but **not on the production path**: `EmbeddingRetrieval` (in-memory numpy,
used by the evals) and `HybridRetrieval` (BM25 + vector, min-max-normalised, `alpha=0.5`,
used by `eval/insurance_eval.py` to show BM25 catching rare terms like "subrogation").

## Why these choices

- **Two-stage retrieve → rerank.** A bi-encoder is fast but coarse; the cross-encoder reads query
  and chunk together and is far more precise. Retrieving 100 then reranking to 3 keeps recall high
  and the prompt small (≈700 tokens per question, ≈$0.0002).
- **1000/200 chunking.** Big enough that a fact keeps its surrounding context (a leave policy plus
  its exceptions), overlap so a fact straddling a boundary appears whole in one chunk.
- **Content-hash collections.** Idempotent ingestion and no cross-document leakage.
- **Strict cache threshold.** "Who is X?" and "Who is Y?" embed close; 0.92 trades hit-rate for safety.

## Known fix history (why the rerank code looks the way it does)

The reranker used to keep only chunks with score > 0 and, when none qualified, returned a *single*
fallback chunk — collapsing the context to 1 chunk. A real query ("who is the candidate for this
resume?") got a wrong "I don't know" because the right chunk was dropped. It now always returns the
top-`k`, and low relevance is surfaced as an `issues` entry + failure-log row instead of silently
shrinking context. Details: [TRACE_FINDINGS.md](TRACE_FINDINGS.md).

## Quality signal

Every answer carries `quality_signal.label` from the top rerank score:
`strong_match` (≥2), `weak_match` (0–2), `no_relevant_match` (≤0). The A2A comparison and the UI use it.
