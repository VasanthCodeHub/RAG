"""HTTP client for the A2A manager agent."""

import json
import os
import uuid

import requests

BASE_URL = os.getenv("SIMPLE_RAG_API_URL", "http://localhost:8000").rstrip("/")


def run_race(pdf_hash: str, question: str) -> dict:
    request_body = {
        "jsonrpc": "2.0",
        "id": uuid.uuid4().hex,
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "messageId": uuid.uuid4().hex,
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": json.dumps({"pdf_hash": pdf_hash, "question": question}),
                    }
                ],
            }
        },
    }
    response = requests.post(f"{BASE_URL}/a2a/manager", json=request_body, timeout=360)
    response.raise_for_status()
    rpc = response.json()
    if rpc.get("error"):
        raise RuntimeError(f"A2A manager failed: {rpc['error'].get('message', 'unknown error')}")
    task = rpc.get("result", {})
    parts = [
        part.get("text")
        for artifact in task.get("artifacts", [])
        for part in artifact.get("parts", [])
        if part.get("kind") == "text"
    ]
    if not parts:
        raise RuntimeError("A2A manager returned no result artifact.")
    result = json.loads(parts[0])
    if not isinstance(result, dict) or not {"team", "single", "metrics"} <= result.keys():
        raise RuntimeError("A2A manager returned an incomplete race result.")
    return result
