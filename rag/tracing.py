import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

LOGGER_NAME = "rag"
DEFAULT_TRACE_FILE = "eval/trace_report.json"
TRACE_PREVIEW_CHARS = 300

_configured = False


def configure_logging() -> None:
    """Set up console (and optional file) logging for the `rag` package.

    Controlled via env vars so behavior can change without touching code:
    - RAG_LOG_LEVEL: DEBUG, INFO, WARNING, ... (default INFO)
    - RAG_LOG_FILE: if set, also write logs to this file path
    """
    global _configured
    if _configured:
        return
    _configured = True

    level = os.getenv("RAG_LOG_LEVEL", "INFO").upper()
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    log_file = os.getenv("RAG_LOG_FILE")
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


def new_trace_id() -> str:
    return uuid.uuid4().hex[:8]


def _format_fields(fields: dict) -> str:
    return " ".join(f"{key}={value!r}" for key, value in fields.items())


@contextmanager
def traced_stage(logger: logging.Logger, name: str, **context):
    """Context manager that logs the start/end/duration of a pipeline stage.

    Yields a mutable `info` dict -- add fields to it inside the `with` block
    and they will be included in the completion log line. On exception, logs
    the failure with duration before re-raising, so timeouts/errors show up
    in the trace instead of only surfacing as a bare stack trace.
    """
    info: dict = {}
    start = time.perf_counter()
    logger.debug("stage=%s status=start %s", name, _format_fields(context))
    try:
        yield info
    except Exception as error:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.error(
            "stage=%s status=error duration_ms=%.1f error=%r %s",
            name,
            duration_ms,
            error,
            _format_fields(context),
        )
        raise
    else:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "stage=%s status=ok duration_ms=%.1f %s %s",
            name,
            duration_ms,
            _format_fields(context),
            _format_fields(info),
        )


def trace_file_path():
    """Where to append live query traces, or None if disabled.

    Controlled via RAG_TRACE_FILE: unset -> DEFAULT_TRACE_FILE, set to a
    path -> that path, set to an empty string -> tracing disabled.
    """
    path = os.getenv("RAG_TRACE_FILE", DEFAULT_TRACE_FILE)
    return path or None


def preview_text(text: str, limit: int = TRACE_PREVIEW_CHARS) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def detect_issues(retrieved_docs, reranked_docs, scores, answer):
    """Inspect one query's real pipeline output and flag concrete problems.

    Returns (issues, top_score).
    """
    issues = []
    if not retrieved_docs:
        issues.append(
            {
                "stage": "retrieve",
                "type": "empty_retrieval",
                "detail": "No documents were retrieved for this query.",
            }
        )

    top_score = float(scores[0]) if scores else None
    if top_score is not None and top_score <= 0:
        issues.append(
            {
                "stage": "rerank",
                "type": "low_relevance",
                "detail": (
                    f"Top rerank score is {round(top_score, 4)} (<= 0): no retrieved "
                    "chunk was judged actually relevant to the query -- the reranker "
                    "fell back to returning its best (still irrelevant) match."
                ),
            }
        )

    if not reranked_docs:
        issues.append(
            {
                "stage": "rerank",
                "type": "empty_context",
                "detail": "No context chunks survived reranking; the LLM answered with no grounding.",
            }
        )

    if not answer or not answer.strip():
        issues.append(
            {
                "stage": "generate",
                "type": "empty_answer",
                "detail": "The LLM returned an empty answer.",
            }
        )

    return issues, top_score


def record_query_trace(query_id: str, record: dict) -> None:
    """Append one real query's full trace to the live trace JSON file.

    Reads the existing file (if any), appends this query, and writes it
    back -- so the file always holds one growing array of *real* queries
    that were actually asked through the app, not synthetic examples.
    """
    path = trace_file_path()
    if not path:
        return

    logger = logging.getLogger(LOGGER_NAME)
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {}
        else:
            data = {}
        data.setdefault("queries", []).append(record)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as error:
        logger.warning(
            "query_id=%s stage=trace_record status=error error=%r", query_id, error
        )
