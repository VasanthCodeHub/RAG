"""In-memory registry of ingested documents' pipelines, keyed by PDF hash.

This is a plain module-level dict, not a database -- proportionate for a
local, single-user tool where the FastAPI process is the one long-lived
thing holding built `SimpleRAGPipeline` instances (Streamlit reruns no
longer need to, since ingestion now happens server-side).
"""

_PIPELINES: dict[str, dict] = {}


def get(pdf_hash: str) -> dict | None:
    return _PIPELINES.get(pdf_hash)


def put(pdf_hash: str, entry: dict) -> None:
    _PIPELINES[pdf_hash] = entry
