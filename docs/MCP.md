# MCP (`mcp_server/`)

[Model Context Protocol](https://modelcontextprotocol.io) lets any compatible host (Claude
Desktop, Claude Code, our agents) discover and call the app's capabilities in a standard way.

## Server — `mcp_server/server.py`

Built with the `mcp` SDK (`MCPServer("simple-rag")`), **stdio transport**. It is a thin proxy of the
FastAPI backend (the backend owns model loading and the vector store), so every client gets
identical pipeline behaviour.

| Tool | Args | Returns |
|---|---|---|
| `ingest_pdf` | `pdf_path` (file readable by the backend), optional `groq_api_key` | `pdf_hash`, `filename`, `n_chunks`, `from_cache` |
| `ask_pdf` | `pdf_hash`, `question` | `answer`, `contexts`, `quality_signal`, `status`, `usage`, `duration_ms` |

Despite the `pdf` in the names, they accept any supported document type (the name is kept so
existing MCP host configs keep working). Errors are returned as `{"error": ...}` with an
actionable message (e.g. "could not reach the RAG API at … start it with …"), never a stack trace.

## Client — `mcp_server/client.py`

`list_tools()` / `call_tool(name, args)` spawn the server as a subprocess per call
(stateless, simple) using `mcp.Client` + `StdioServerParameters`. Used by:

- `backend/routers/mcp_routes.py` → the MCP page in the UI (`GET /mcp/tools`, `POST /mcp/call`)
- `agent/document_agent.py` → the agent's `search_document` tool
- `a2a/manager.py` → every specialist and the single-MCP baseline

Trade-off: a subprocess per call costs ≈1 s of startup. That is visible in agent/A2A latency and is
the first thing to fix (persistent session) if latency matters.

## Connect an external host

```json
{
  "mcpServers": {
    "simple-rag": {
      "command": "<repo>/.venv/Scripts/python.exe",
      "args": ["-m", "mcp_server.server"],
      "cwd": "<repo>",
      "env": { "GROQ_API_KEY": "..." }
    }
  }
}
```

The backend must be running (`python run.py`). Inspect interactively:
`.venv/Scripts/python.exe -m mcp dev mcp_server/server.py`.
