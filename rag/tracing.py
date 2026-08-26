import logging
import os
import time
import uuid
from contextlib import contextmanager

LOGGER_NAME = "rag"

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
