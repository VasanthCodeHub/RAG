"""Small helpers for the A2A JSON-RPC message/send protocol."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

API_BASE_URL = "http://localhost:8000"

AGENTS = {
    "manager": {
        "name": "Document Research Manager",
        "description": "Delegates document questions to two specialists and compares their work with a direct MCP answer.",
        "skill": "Coordinate document research, evidence review, and a direct MCP baseline.",
    },
    "document-answer": {
        "name": "Document Answer Specialist",
        "description": "Uses the Simple RAG MCP ask_pdf tool to answer a document question directly.",
        "skill": "Find and answer the user's question from the ingested document.",
    },
    "evidence-reviewer": {
        "name": "Evidence Review Specialist",
        "description": "Uses the Simple RAG MCP ask_pdf tool to check supporting passages, conditions, and caveats.",
        "skill": "Independently verify document evidence and relevant qualifications.",
    },
}


def agent_card(agent_name: str, base_url: str = API_BASE_URL) -> dict[str, Any]:
    agent = AGENTS[agent_name]
    return {
        "protocolVersion": "0.3.0",
        "name": agent["name"],
        "description": agent["description"],
        "url": f"{base_url.rstrip('/')}/a2a/{agent_name}",
        "version": "1.0.0",
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": agent_name,
                "name": agent["name"],
                "description": agent["skill"],
                "tags": ["document", "rag", "mcp"],
                "examples": ["Answer a question using an ingested PDF."],
            }
        ],
    }


def task_response(result: dict[str, Any], context_id: str | None = None) -> dict[str, Any]:
    """Wrap an agent result as a completed A2A Task with a text artifact."""
    return {
        "kind": "task",
        "id": uuid.uuid4().hex,
        "contextId": context_id or uuid.uuid4().hex,
        "status": {"state": "completed", "timestamp": datetime.now(timezone.utc).isoformat()},
        "artifacts": [
            {
                "artifactId": uuid.uuid4().hex,
                "name": "result",
                "parts": [{"kind": "text", "text": json.dumps(result, ensure_ascii=False)}],
            }
        ],
    }


def message_text(message: Any) -> str:
    if not isinstance(message, dict) or message.get("role") != "user":
        raise ValueError("message must be a user message")
    parts = message.get("parts")
    if not isinstance(parts, list):
        raise ValueError("message.parts must be a list")
    text_parts = [
        part["text"]
        for part in parts
        if isinstance(part, dict) and part.get("kind") == "text" and isinstance(part.get("text"), str)
    ]
    if not text_parts:
        raise ValueError("message must contain a text part")
    return "\n".join(text_parts)
