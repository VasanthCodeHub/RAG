# Simple RAG — MCP server

Exposes this app's document Q&A capability over MCP: ingest a PDF, then ask
questions about it. It's a thin client of the existing FastAPI backend
(`api/main.py`), so start that first.

## Run

```bash
# Terminal 1 — the RAG API backend this server proxies to
.venv/Scripts/python.exe -m uvicorn api.main:app --port 8000

# Terminal 2 — smoke-test the MCP server with the MCP inspector
.venv/Scripts/python.exe -m mcp dev mcp_server/server.py
```

## Connect from an MCP host

Add to the host's MCP config (e.g. Claude Desktop's `claude_desktop_config.json`,
or Claude Code's `.mcp.json`):

```json
{
  "mcpServers": {
    "simple-rag": {
      "command": "D:/vasanth/rag/simple-rag/.venv/Scripts/python.exe",
      "args": ["-m", "mcp_server.server"],
      "cwd": "D:/vasanth/rag/simple-rag",
      "env": {
        "GROQ_API_KEY": "your-key-here"
      }
    }
  }
}
```

`GROQ_API_KEY` is optional here if `ingest_pdf` is always called with an
explicit `groq_api_key` argument; otherwise the server falls back to this
environment variable.

## Tools

- **`ingest_pdf(pdf_path, groq_api_key=None)`** — chunks and embeds a PDF
  into the persistent vector store. Returns `pdf_hash`, `n_chunks`,
  `from_cache`. Re-ingesting the same file is served from cache.
- **`ask_pdf(pdf_hash, question)`** — runs the retrieval → rerank →
  generation pipeline and returns `answer`, `contexts`, `quality_signal`,
  `status`.

`RAG_API_BASE_URL` overrides the backend URL (default `http://localhost:8000`).
