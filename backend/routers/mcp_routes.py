"""Expose the MCP server to the browser: list its tools and call them.
The backend talks to the MCP server over stdio (mcp_server/client.py)."""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mcp_server.client import call_tool, list_tools

router = APIRouter(prefix="/mcp", tags=["mcp"])


class CallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


@router.get("/tools")
async def tools():
    try:
        return await asyncio.to_thread(list_tools)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"MCP server unavailable: {exc}")


@router.post("/call")
async def call(req: CallRequest):
    try:
        return await asyncio.to_thread(call_tool, req.name, req.arguments)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"MCP call failed: {exc}")
