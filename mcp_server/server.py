"""MCP server exposing this app's RAG capability: ingest a PDF, then ask
questions about it.

Thin wrapper around the existing FastAPI backend (`api/main.py`) rather than
a reimplementation -- the backend already owns model loading and the
persistent Chroma store, so this process stays small and any other client
(Streamlit, this MCP server, a future one) shares the exact same pipeline
behavior.

Run the backend first:
    .venv/Scripts/python.exe -m uvicorn backend.main:app --port 8000

Then run this server (stdio transport, for an MCP host to launch directly):
    .venv/Scripts/python.exe -m mcp_server.server

Or point an MCP host's config at this module -- see mcp_server/README.md.
"""

import os

import httpx
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

load_dotenv()

API_BASE_URL = os.getenv("RAG_API_BASE_URL", "http://localhost:8000")
DEFAULT_GROQ_API_KEY = os.getenv("GROQ_API_KEY")

mcp = MCPServer("simple-rag")


def _api_error(prefix: str, exc: Exception) -> str:
    if isinstance(exc, httpx.ConnectError):
        return (
            f"{prefix}: could not reach the RAG API at {API_BASE_URL}. "
            "Start it with: .venv/Scripts/python.exe -m uvicorn backend.main:app --port 8000"
        )
    if isinstance(exc, httpx.HTTPStatusError):
        return f"{prefix}: {exc.response.status_code} {exc.response.text}"
    return f"{prefix}: {exc}"


@mcp.tool()
def ingest_pdf(pdf_path: str, groq_api_key: str | None = None) -> dict:
    """Ingest a PDF file so it can be queried with ask_pdf.

    Chunks and embeds the document into the app's persistent vector store.
    Re-ingesting a PDF that was already processed is cheap -- it's detected
    by content hash and served from cache instead of re-embedding.

    Args:
        pdf_path: Absolute path to a PDF file on disk, readable by the RAG
            API server process.
        groq_api_key: Groq API key used for this document's pipeline. Falls
            back to the GROQ_API_KEY environment variable if omitted.

    Returns:
        A dict with pdf_hash (pass this to ask_pdf), filename, n_chunks, and
        from_cache.
    """
    api_key = groq_api_key or DEFAULT_GROQ_API_KEY
    if not api_key:
        return {
            "error": "No Groq API key available. Pass groq_api_key or set "
            "GROQ_API_KEY in the environment running this MCP server."
        }
    # Strip surrounding quotes -- Windows' "Copy as path" wraps the value in
    # literal double quotes, which isfile() would otherwise reject outright.
    pdf_path = pdf_path.strip().strip('"').strip("'")
    if not os.path.isfile(pdf_path):
        return {"error": f"No such file: {pdf_path}"}

    try:
        with open(pdf_path, "rb") as f:
            response = httpx.post(
                f"{API_BASE_URL}/documents",
                files={"file": (os.path.basename(pdf_path), f, "application/pdf")},
                data={"groq_api_key": api_key},
                timeout=120.0,
            )
        response.raise_for_status()
    except Exception as exc:
        return {"error": _api_error("ingest_pdf failed", exc)}

    return response.json()


@mcp.tool()
def ask_pdf(pdf_hash: str, question: str) -> dict:
    """Ask a question about a PDF that was already ingested with ingest_pdf.

    Runs the app's full RAG pipeline (retrieval, rerank, generation) and
    returns the answer along with the supporting context and a quality
    signal indicating how well the retrieved chunks matched the question.

    Args:
        pdf_hash: The pdf_hash returned by ingest_pdf.
        question: The question to ask about the document.

    Returns:
        A dict with answer, contexts, quality_signal, and status.
    """
    try:
        response = httpx.post(
            f"{API_BASE_URL}/query",
            json={"pdf_hash": pdf_hash, "query": question},
            timeout=120.0,
        )
        response.raise_for_status()
    except Exception as exc:
        return {"error": _api_error("ask_pdf failed", exc)}

    body = response.json()
    return {
        "answer": body["answer"],
        "contexts": body["contexts"],
        "quality_signal": body["quality_signal"],
        "status": body["status"],
        "usage": body.get("usage"),
        "duration_ms": body.get("total_duration_ms"),
    }


if __name__ == "__main__":
    mcp.run()
