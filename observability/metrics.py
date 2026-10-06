"""Observability: structured logs, per-query metrics (latency/tokens/cost),
and a failure log that feeds the failure -> regression-test loop.

Three append-only JSONL files live under RAG_LOG_DIR (default `logs/`):
- app.jsonl      every log line from the `rag` and `api` loggers, one JSON
                 object per line, each stamped with `query_id`/`request_id`
                 (see JsonFormatter + ContextFilter) so one question's whole
                 journey can be filtered with a single field.
- queries.jsonl  one metrics row per answered/failed query (see
                 record_query_metrics) -- the source for the dashboard.
- failures.jsonl queries that went wrong (detected issues, exceptions, or a
                 human low rating). `eval/failure_loop.py` promotes these
                 into permanent regression cases.
"""

import json
import logging
import os
import statistics
import threading
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("rag.observability")

query_id_var: ContextVar[str] = ContextVar("query_id", default="-")
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "query_id",
    "request_id",
}
_lock = threading.Lock()


class ContextFilter(logging.Filter):
    """Stamps every record with the current query_id/request_id contextvars,
    so lines logged deep in llm.py/retrieval.py carry the id without it
    being threaded through every function signature.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.query_id = query_id_var.get()
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "query_id": getattr(record, "query_id", "-"),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def log_dir() -> Path:
    return Path(os.getenv("RAG_LOG_DIR", "logs"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# JSONL helpers
# ---------------------------------------------------------------------------


def _append(path: Path, row: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock, open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except OSError as error:
        logger.warning("observability write failed path=%s error=%r", path, error)


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a torn/partial line must not take the dashboard down
    return rows


def _rewrite(path: Path, rows: list[dict]) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Per-query metrics
# ---------------------------------------------------------------------------


def queries_path() -> Path:
    return log_dir() / "queries.jsonl"


def failures_path() -> Path:
    return log_dir() / "failures.jsonl"


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def record_query_metrics(
    record: dict,
    *,
    pdf_hash: str | None = None,
    cache: dict | None = None,
    error: str | None = None,
) -> dict:
    """Flatten one pipeline trace into a metrics row and append it.

    Also raises `slow_query` / `expensive_query` alerts (WARNING log + flag
    on the row) against RAG_SLOW_QUERY_MS (default 8000) and
    RAG_QUERY_COST_WARN_USD (default 0.01).
    """
    steps = record.get("steps", {})
    usage = record.get("usage") or {}
    cache = cache or {}
    row = {
        "query_id": record.get("query_id"),
        "ts": record.get("timestamp") or _now(),
        "pdf_hash": pdf_hash,
        "query": record.get("query"),
        "status": "error" if error else record.get("status", "ok"),
        "error": error,
        "cache_hit": bool(cache.get("hit")),
        "cache_similarity": cache.get("similarity"),
        "total_ms": record.get("total_duration_ms"),
        "retrieve_ms": steps.get("retrieve", {}).get("duration_ms"),
        "rerank_ms": steps.get("rerank", {}).get("duration_ms"),
        "generate_ms": steps.get("generate", {}).get("duration_ms"),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "cost_usd": usage.get("estimated_cost_usd", 0.0) or 0.0,
        "saved_cost_usd": cache.get("saved_cost_usd", 0.0),
        "top_score": steps.get("rerank", {}).get("top_score"),
        "issues": [i.get("type") for i in record.get("issues", [])],
        "alerts": [],
    }
    if (row["total_ms"] or 0) > _float_env("RAG_SLOW_QUERY_MS", 8000):
        row["alerts"].append("slow_query")
    if row["cost_usd"] > _float_env("RAG_QUERY_COST_WARN_USD", 0.01):
        row["alerts"].append("expensive_query")
    for alert in row["alerts"]:
        logger.warning(
            "alert=%s total_ms=%s cost_usd=%.5f",
            alert,
            row["total_ms"],
            row["cost_usd"],
            extra={"event": "alert", "alert": alert},
        )
    logger.info(
        "query_metrics status=%s cache_hit=%s total_ms=%s cost_usd=%.5f",
        row["status"],
        row["cache_hit"],
        row["total_ms"],
        row["cost_usd"],
        extra={
            "event": "query_metrics",
            "prompt_tokens": row["prompt_tokens"],
            "completion_tokens": row["completion_tokens"],
            "cache_hit": row["cache_hit"],
        },
    )
    _append(queries_path(), row)
    return row


def list_queries(limit: int = 100) -> list[dict]:
    rows = _read(queries_path())
    return rows[-limit:][::-1]  # newest first


def find_query(query_id: str) -> dict | None:
    for row in reversed(_read(queries_path())):
        if row.get("query_id") == query_id:
            return row
    return None


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))
    return round(ordered[idx], 1)


def _avg(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 1) if values else None


def summarize(rows: list[dict] | None = None) -> dict:
    """Aggregate dashboard numbers: volume, latency percentiles, tokens,
    spend, and how much the semantic cache saved.
    """
    rows = _read(queries_path()) if rows is None else rows
    total = len(rows)
    hits = [r for r in rows if r.get("cache_hit")]
    misses = [r for r in rows if not r.get("cache_hit") and r.get("status") != "error"]
    latencies = [r["total_ms"] for r in rows if r.get("total_ms") is not None]
    issue_counts: dict[str, int] = {}
    for r in rows:
        for issue in r.get("issues", []):
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

    def stage_avg(key):
        return _avg([r[key] for r in misses if r.get(key) is not None])

    return {
        "queries": total,
        "errors": sum(1 for r in rows if r.get("status") == "error"),
        "with_issues": sum(1 for r in rows if r.get("issues")),
        "cache_hits": len(hits),
        "cache_hit_rate": round(len(hits) / total, 3) if total else 0.0,
        "prompt_tokens": sum(r.get("prompt_tokens") or 0 for r in rows),
        "completion_tokens": sum(r.get("completion_tokens") or 0 for r in rows),
        "total_cost_usd": round(sum(r.get("cost_usd") or 0 for r in rows), 6),
        "saved_cost_usd": round(sum(r.get("saved_cost_usd") or 0 for r in rows), 6),
        "avg_cost_per_llm_call_usd": (
            round(sum(r.get("cost_usd") or 0 for r in misses) / len(misses), 6) if misses else None
        ),
        "latency_ms": {
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
            "avg_cache_hit": _avg([r["total_ms"] for r in hits if r.get("total_ms") is not None]),
            "avg_cache_miss": _avg([r["total_ms"] for r in misses if r.get("total_ms") is not None]),
        },
        "stage_avg_ms": {
            "retrieve": stage_avg("retrieve_ms"),
            "rerank": stage_avg("rerank_ms"),
            "generate": stage_avg("generate_ms"),
        },
        "issue_counts": issue_counts,
        "alerts": sum(len(r.get("alerts", [])) for r in rows),
    }


# ---------------------------------------------------------------------------
# Failure log (input to the failure -> test loop)
# ---------------------------------------------------------------------------


def record_failure(
    query_id: str,
    kind: str,
    *,
    query: str | None = None,
    answer: str | None = None,
    pdf_hash: str | None = None,
    detail: str | None = None,
    issues: list[dict] | None = None,
    extra: dict | None = None,
) -> dict:
    """Log one failed query. A query that fails for several reasons (e.g. a
    detected issue *and* a low human rating) stays one row with every kind
    listed, so promotion produces one test, not duplicates.
    """
    path = failures_path()
    with _lock:
        rows = _read(path)
        existing = next((r for r in rows if r["query_id"] == query_id), None)
        if existing:
            if kind not in existing["kinds"]:
                existing["kinds"].append(kind)
            for key, value in (("query", query), ("answer", answer), ("pdf_hash", pdf_hash)):
                if value and not existing.get(key):
                    existing[key] = value
            if detail:
                existing["details"].append(detail)
            if extra:
                existing.setdefault("extra", {}).update(extra)
            row = existing
        else:
            row = {
                "query_id": query_id,
                "ts": _now(),
                "kinds": [kind],
                "query": query,
                "answer": answer,
                "pdf_hash": pdf_hash,
                "details": [detail] if detail else [],
                "issues": issues or [],
                "extra": extra or {},
                "status": "open",
            }
            rows.append(row)
        path.parent.mkdir(parents=True, exist_ok=True)
        _rewrite(path, rows)
    logger.warning(
        "failure_recorded kind=%s",
        kind,
        extra={"event": "failure", "failure_kind": kind, "failed_query_id": query_id},
    )
    return row


def list_failures(status: str | None = None) -> list[dict]:
    rows = _read(failures_path())
    if status:
        rows = [r for r in rows if r.get("status") == status]
    return rows[::-1]


def get_failure(query_id: str) -> dict | None:
    return next((r for r in _read(failures_path()) if r["query_id"] == query_id), None)


def mark_failure_promoted(query_id: str, case_id: str) -> None:
    with _lock:
        rows = _read(failures_path())
        for row in rows:
            if row["query_id"] == query_id:
                row["status"] = "promoted"
                row["case_id"] = case_id
        _rewrite(failures_path(), rows)
