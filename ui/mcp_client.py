"""Thin MCP client wrapping mcp_server/server.py, used by pages/4_MCP.py to
discover and call its tools the real MCP way (stdio transport, JSON-RPC
under the hood) instead of hard-coding them -- same idea as
ui/api_client.py, but talking MCP instead of plain HTTP.

Each call spins up a fresh subprocess + session (simple and stateless,
matching how a one-off client would use this server) rather than keeping a
long-lived connection across Streamlit reruns.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_SCRIPT = PROJECT_ROOT / "mcp_server" / "server.py"


def _server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
        cwd=str(PROJECT_ROOT),
    )


async def _list_tools_async() -> dict[str, Any]:
    async with Client(_server_params()) as client:
        result = await client.list_tools()
        return {
            "server_info": {
                "name": client.server_info.name if client.server_info else "simple-rag",
                "protocol_version": client.protocol_version,
            },
            "tools": [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": t.input_schema,
                }
                for t in result.tools
            ],
        }


async def _call_tool_async(name: str, arguments: dict) -> dict[str, Any]:
    async with Client(_server_params()) as client:
        result = await client.call_tool(name, arguments)
        text = "\n".join(block.text for block in result.content if hasattr(block, "text"))
        try:
            parsed = json.loads(text) if text else None
        except json.JSONDecodeError:
            parsed = None
        return {
            "is_error": bool(result.is_error),
            "structured_content": result.structured_content,
            "parsed": parsed,
            "raw_text": text,
        }


def list_tools() -> dict[str, Any]:
    return asyncio.run(_list_tools_async())


def call_tool(name: str, arguments: dict) -> dict[str, Any]:
    return asyncio.run(_call_tool_async(name, arguments))
