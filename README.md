# Simple RAG

Ask questions about a PDF (e.g. your resume) using a small retrieval-augmented
generation pipeline: embedding-based (vector) retrieval, cross-encoder
reranking, and Groq for the answer.

## Pre-requisites

- Python 3.9+
- Poppler (needed for PDF text extraction)

Install Poppler:
```bash
# Debian/Ubuntu
sudo apt install build-essential libpoppler-cpp-dev pkg-config python3-dev

# Fedora/RHEL
sudo yum install gcc-c++ pkgconfig poppler-cpp-devel python3-devel

# macOS
brew install pkg-config poppler python

# Windows (using conda)
conda install -c conda-forge poppler
```

## Setup

```bash
pip install -e .
cp .env.example .env
```

Add your Groq API key to `.env` (get one at https://console.groq.com/keys):
```
GROQ_API_KEY=your-key-here
```

## Usage

Drop your PDF in the project root as `resume.pdf`, then run:
```bash
python main.py
```

Or point it at any PDF:
```bash
python main.py path/to/file.pdf
```

You'll get a prompt to ask questions about the document.

## Web UI (FastAPI backend + Streamlit frontend)

The web UI is two processes: a FastAPI backend (pipeline, vector DB, judge, eval)
and a Streamlit frontend that talks to it over HTTP. Run both, in two terminals:

```bash
# Terminal 1 — API backend (loads the embedding/rerank models on first request)
.venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000

# Terminal 2 — Streamlit frontend
.venv/Scripts/python.exe -m streamlit run app.py --server.port 8501
```

Open http://localhost:8501. Upload a PDF, ask questions, and use "Rate this
answer" to run the LLM judge and add your own score. The **Evaluation** page
(in the sidebar nav) runs the judge calibration check and the before/after
regression suite, and shows every rating you've saved.

The **A2A Team** page compares a manager that delegates parallel work to two
document specialists with a single direct MCP answer. Both paths call the
existing `ask_pdf` MCP tool. The API advertises its manager at
`/.well-known/agent-card.json`, lists agents at `/a2a/agents`, and accepts the
A2A JSON-RPC `message/send` method at `/a2a/{agent_name}`. Start the FastAPI
backend and Streamlit frontend as above; ingest a PDF on the chat or MCP page,
then open A2A Team to run the comparison. Token counts use Groq usage metadata;
cost is an estimate for `openai/gpt-oss-120b` at the rates documented on the
page.

Uploaded PDFs are chunked and embedded into a persistent [Chroma](https://www.trychroma.com/)
collection under `.chroma_data/`, keyed by a hash of the file's bytes — so
re-uploading the same PDF (even after restarting the backend) skips
re-embedding entirely.

## MCP server

`mcp_server/` exposes document ingestion and Q&A as MCP tools, so any MCP
host (Claude Desktop, Claude Code, another agent) can call this app's RAG
pipeline directly. See [`mcp_server/README.md`](mcp_server/README.md) for
setup.

## Observability, cost & the failure -> test loop

- **Logs**: `logs/app.jsonl` (rotating, one JSON object per line). Every line from the `rag`/`api` loggers carries `query_id` and `request_id`, so `grep <query_id> logs/app.jsonl` shows one question's whole journey (cache lookup, retrieve, rerank, generate, retries, errors). Each HTTP response also returns an `x-request-id` header.
- **Metrics**: `logs/queries.jsonl` has one row per query (stage latencies, tokens, cost, cache hit, issues, `slow_query`/`expensive_query` alerts). The **Observability** page (`pages/6_Observability.py`) shows p50/p95 latency, spend, and what the cache saved.
- **Semantic cache** (`rag/semantic_cache.py`): repeat or near-duplicate questions on the same document + model are answered from cache with zero tokens. Exact normalized match first, then embedding cosine >= `RAG_CACHE_THRESHOLD` (default 0.92). Only clean answers are cached (no detected issues). `POST /query` accepts `use_cache=false` to bypass it. Clear it from the Observability page.
- **Failure -> test loop**: failures (detected issues, exceptions, human ratings <= 2) are logged to `logs/failures.jsonl`. On the Observability page, promote one and state what a correct answer must contain; it is pinned in `eval/failure_cases.jsonl`. Replay all pinned cases against the real pipeline with `python -m eval.failure_loop`; the same cases run in `python -m unittest tests.test_observability` when `GROQ_API_KEY` is set.

All knobs are in `.env.example`.
