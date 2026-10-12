import json
import logging
import os
import re
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

    # Structured JSON logs (rotating) for both the pipeline (`rag`) and the
    # API/A2A layer (`api`); every line carries query_id/request_id.
    # RAG_JSON_LOG=0 turns this off.
    from logging.handlers import RotatingFileHandler

    from .metrics import ContextFilter, JsonFormatter, log_dir

    context_filter = ContextFilter()
    stream_handler.addFilter(context_filter)
    stream_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s [q=%(query_id)s r=%(request_id)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    api_logger = logging.getLogger("api")
    api_logger.setLevel(level)
    api_logger.addHandler(stream_handler)
    if os.getenv("RAG_JSON_LOG", "1").lower() not in ("0", "false", "no"):
        log_dir().mkdir(parents=True, exist_ok=True)
        json_handler = RotatingFileHandler(
            log_dir() / "app.jsonl", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
        )
        json_handler.setFormatter(JsonFormatter())
        json_handler.addFilter(context_filter)
        logger.addHandler(json_handler)
        api_logger.addHandler(json_handler)


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


_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "are", "was", "were", "you", "your", "can",
    "may", "must", "will", "from", "have", "has", "not", "only", "any", "all", "per", "than",
    "which", "their", "them", "its", "also", "but", "who", "what", "when", "how", "does",
    "should", "would", "could", "about", "into", "such", "these", "those", "there", "here",
}
_NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
}
GROUNDED_MIN_OVERLAP = 0.6


def _content_tokens(text: str) -> set[str]:
    """Lower-cased words/numbers worth checking, with spelled-out numbers
    folded to digits ("three" == "3") so a paraphrase still matches.
    """
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    tokens = [_NUMBER_WORDS.get(t, t) for t in tokens]
    return {t for t in tokens if t not in _STOPWORDS and (len(t) > 2 or t.isdigit())}


def answer_is_grounded(answer: str, contexts: list[str]) -> bool:
    """Cheap, no-LLM check that the answer's content words/numbers come from
    the context it was given (>= GROUNDED_MIN_OVERLAP of them).
    """
    wanted = _content_tokens(answer)
    if not wanted:
        return False
    available = _content_tokens(" ".join(contexts))
    return len(wanted & available) / len(wanted) >= GROUNDED_MIN_OVERLAP


def detect_issues(retrieved_docs, reranked_docs, scores, answer):
    """Inspect one query's real pipeline output and flag concrete problems.

    A rerank score <= 0 alone is *not* a failure: the cross-encoder scores
    short factual questions low even when the right chunk was used, and a
    correct "the document doesn't say" refusal also scores low. It is only
    flagged when the answer is neither a refusal nor supported by the
    context (see failure `831f3491`, docs/SUPPORT_DRILL.md).

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
    from eval.judges import looks_like_refusal  # lazy: eval imports this package

    low_score_ok = bool(answer) and (
        looks_like_refusal(answer) or answer_is_grounded(answer, reranked_docs or [])
    )
    if top_score is not None and top_score <= 0 and low_score_ok:
        logging.getLogger("rag.tracing").info(
            "low_rerank_score_but_answer_ok top_score=%.4f", top_score
        )
    elif top_score is not None and top_score <= 0:
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
