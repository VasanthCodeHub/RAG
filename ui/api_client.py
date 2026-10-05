"""Thin HTTP client wrapping the FastAPI backend (see api/main.py). Both
Streamlit pages (app.py, pages/1_Evaluation.py) talk to the pipeline and the
eval tooling only through these functions -- no direct rag/eval imports.
"""

import os

import requests

BASE_URL = os.getenv("SIMPLE_RAG_API_URL", "http://localhost:8000")


def ingest_document(pdf_bytes: bytes, filename: str, api_key: str) -> dict:
    response = requests.post(
        f"{BASE_URL}/documents",
        files={"file": (filename, pdf_bytes, "application/pdf")},
        data={"groq_api_key": api_key},
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def run_query(pdf_hash: str, query: str) -> dict:
    response = requests.post(
        f"{BASE_URL}/query",
        json={"pdf_hash": pdf_hash, "query": query},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def judge_answer(question: str, contexts: list[str], answer: str, api_key: str) -> dict:
    response = requests.post(
        f"{BASE_URL}/judge",
        json={"question": question, "contexts": contexts, "answer": answer, "groq_api_key": api_key},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def save_rating(rating: dict) -> dict:
    response = requests.post(f"{BASE_URL}/ratings", json=rating, timeout=30)
    response.raise_for_status()
    return response.json()


def list_ratings() -> list[dict]:
    response = requests.get(f"{BASE_URL}/ratings", timeout=30)
    response.raise_for_status()
    return response.json()


def run_calibration(api_key: str) -> dict:
    response = requests.post(f"{BASE_URL}/eval/calibration", json={"groq_api_key": api_key}, timeout=180)
    response.raise_for_status()
    return response.json()


def run_regression(api_key: str) -> dict:
    response = requests.post(f"{BASE_URL}/eval/regression", json={"groq_api_key": api_key}, timeout=300)
    response.raise_for_status()
    return response.json()


def _get(path: str, **params):
    response = requests.get(f"{BASE_URL}/observability{path}", params=params or None, timeout=15)
    response.raise_for_status()
    return response.json()


def obs_summary() -> dict:
    return _get("/summary")


def obs_queries(limit: int = 200) -> list[dict]:
    return _get("/queries", limit=limit)


def obs_failures(status: str | None = None) -> list[dict]:
    return _get("/failures", **({"status": status} if status else {}))


def obs_cases() -> list[dict]:
    return _get("/cases")


def obs_cache() -> dict:
    return _get("/cache")


def obs_promote(query_id: str, should_answer: bool, expected_keyword: str | None, problem_type: str | None) -> dict:
    response = requests.post(
        f"{BASE_URL}/observability/failures/{query_id}/promote",
        json={
            "should_answer": should_answer,
            "expected_keyword": expected_keyword or None,
            "problem_type": problem_type or None,
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def obs_clear_cache() -> dict:
    response = requests.delete(f"{BASE_URL}/observability/cache", timeout=15)
    response.raise_for_status()
    return response.json()
