import logging
import time
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.routers import a2a, documents, eval_routes, health, judge, observability, query, ratings
from rag.observability import request_id_var
from rag.tracing import configure_logging

load_dotenv()
configure_logging()

app = FastAPI(title="Simple RAG API")
request_logger = logging.getLogger("api.request")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """One structured log line per HTTP request, with a request_id that every
    log line emitted while handling it carries (also returned as a header).
    """
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:8]
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        request_logger.exception("%s %s status=500", request.method, request.url.path)
        raise
    else:
        response.headers["x-request-id"] = request_id
        request_logger.info(
            "%s %s status=%d duration_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - start) * 1000,
            extra={"event": "http_request", "status_code": response.status_code},
        )
        return response
    finally:
        request_id_var.reset(token)


# Local single-user dev tool: the `requests` calls from app.py/pages/*.py
# happen server-side (Streamlit's Python process calling this API directly),
# so cross-origin isn't actually in play for that traffic -- this is just
# cheap insurance for anyone opening this API's own /docs in a browser tab.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(query.router)
app.include_router(judge.router)
app.include_router(ratings.router)
app.include_router(eval_routes.router)
app.include_router(a2a.router)
app.include_router(observability.router)
