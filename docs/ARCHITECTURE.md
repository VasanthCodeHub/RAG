# Architecture

One app, seven concerns, each in its own folder. A user uploads **any document**
(PDF, DOCX, TXT, MD, HTML, CSV, JSON), asks questions, and can answer them four
ways — direct RAG, a single tool-calling agent, MCP tools, or an A2A team.

```
                         ┌───────────────────────────────┐
                         │  frontend/  (React + Vite)    │  :5173
                         │  Chat · Evaluation · Agents · │
                         │  MCP · A2A · Observability    │
                         └──────────────┬────────────────┘
                                        │ /api/*  (Vite proxy)
                         ┌──────────────▼────────────────┐
                         │  backend/  (FastAPI)          │  :8000
                         │  routers: documents query     │
                         │  judge ratings eval agent mcp │
                         │  a2a observability            │
                         └─┬───────┬─────────┬─────────┬─┘
                           │       │         │         │
        ┌──────────────────▼┐  ┌───▼──────┐ ┌▼───────┐ ┌▼──────────────┐
        │ rag/              │  │ agent/   │ │ a2a/   │ │ mcp_server/   │
        │ ingest·chunk·     │  │ document │ │ manager│ │ ingest_pdf    │
        │ retrieve·rerank·  │◄─┤ agent +  │ │ + 2    │ │ ask_pdf       │
        │ generate·cache    │  │ claims   │ │ special│ │ (stdio MCP)   │
        └─────────┬─────────┘  │ agent    │ │ ists   │ └───────▲───────┘
                  │            └────┬─────┘ └───┬────┘         │
                  │                 └───────────┴──────────────┘
                  │            (agents reach the RAG only through MCP `ask_pdf`)
        ┌─────────▼─────────┐    ┌──────────────────────┐
        │ observability/    │    │ eval/                │
        │ logs·metrics·cost │───►│ judges·regression·   │
        │ failure log       │    │ failure→test loop·e2e│
        └───────────────────┘    └──────────────────────┘
```

## Folder map

| Folder | Responsibility | Doc |
|---|---|---|
| `frontend/` | React UI (the only UI; Streamlit is gone) | [FRONTEND.md](FRONTEND.md) |
| `backend/` | FastAPI app: HTTP surface + wiring. No business logic beyond request handling | this file |
| `rag/` | The RAG pipeline: readers, chunking, retrieval, rerank, generation, semantic cache | [RAG.md](RAG.md) |
| `mcp_server/` | MCP server exposing `ingest_pdf` / `ask_pdf`, plus the MCP client the backend uses | [MCP.md](MCP.md) |
| `agent/` | Single agents: generic document agent, claims-triage agent + workflow | [AGENT.md](AGENT.md) |
| `a2a/` | Agent-to-Agent protocol helpers and the manager/specialist orchestration | [A2A.md](A2A.md) |
| `eval/` | Judges, regression suite, failure→test loop, end-to-end eval, agent evals | [EVAL.md](EVAL.md) |
| `observability/` | Structured logs, per-query metrics, cost, failure log, traces | [OBSERVABILITY.md](OBSERVABILITY.md) |

## Request lifecycles

**Upload** — `POST /documents` → `rag.data_helper.read_document_bytes` (by extension) →
`text2chunk` (1000 chars / 200 overlap) → embed with `all-MiniLM-L6-v2` → persist in a
Chroma collection named `doc-<sha256[:32]>`. The same bytes uploaded again are a disk read.

**Ask (direct)** — `POST /query` → semantic-cache lookup → Chroma top-100 → cross-encoder
rerank to top-3 → Groq `openai/gpt-oss-120b` with a grounded prompt → issue detection →
metrics + failure log → cache store (clean answers only).

**Ask (agent)** — `POST /agent/document` → agent loop (≤4 iterations) → each sub-question
is an MCP `ask_pdf` call → the MCP server calls `POST /query` → same pipeline as above.

**Ask (A2A)** — `POST /a2a/manager` (JSON-RPC `message/send`) → manager fans out to
`document-answer` and `evidence-reviewer` in parallel (each is an A2A call that ends in MCP
`ask_pdf`) and also runs one direct MCP call; returns both with quality/cost/latency and a winner.

## Design decisions

- **Everything funnels through one pipeline.** Chat, MCP, agent and A2A all end in
  `SimpleRAGPipeline.run`, so there is one behaviour to evaluate, cache and observe.
- **Agents use MCP, not imports.** The agent/A2A layers call tools over MCP instead of importing
  `rag/`, which keeps them swappable and matches how an external host would use the app.
- **State**: document vectors persist on disk (Chroma); the pipeline registry is in memory but is
  *rehydrated lazily* from disk on the first query after a restart (`documents.rehydrate`).
- **Document-agnostic by construction**: nothing in `rag/`, `backend/` or the prompts mentions
  resumes; the only document-specific code is the reader chosen by file extension.
- **Retrieval was deliberately left untouched** while restructuring — `rag/retrieval.py`,
  `rag/rerank.py`, `rag/pipeline.py` are byte-for-byte the pre-merge logic (only import paths changed).

## Ports and env

| Var | Purpose |
|---|---|
| `GROQ_API_KEY` | LLM key (server-side). The UI may also send one per request |
| `SIMPLE_RAG_API_URL` | Where A2A/MCP clients reach the backend (default `http://localhost:8000`) |
| `RAG_LOG_DIR`, `RAG_LOG_LEVEL`, `RAG_SLOW_QUERY_MS`, `RAG_QUERY_COST_WARN_USD` | Observability |
| `RAG_CACHE_ENABLED`, `RAG_CACHE_THRESHOLD`, `RAG_CACHE_TTL_S` | Semantic cache |
