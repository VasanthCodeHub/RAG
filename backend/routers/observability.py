"""Read-only dashboards over the observability logs, the semantic cache, and
the failure -> regression-case promotion endpoint.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from eval import failure_loop
from observability import metrics as observability
from rag.semantic_cache import get_shared_cache

router = APIRouter(prefix="/observability", tags=["observability"])


class PromoteRequest(BaseModel):
    should_answer: bool = True
    expected_keyword: str | list[str] | None = None
    problem_type: str | None = None


@router.get("/summary")
def summary():
    return observability.summarize()


@router.get("/queries")
def queries(limit: int = 100):
    return observability.list_queries(limit=min(limit, 1000))


@router.get("/failures")
def failures(status: str | None = None):
    return observability.list_failures(status)


@router.post("/failures/{query_id}/promote")
def promote(query_id: str, req: PromoteRequest):
    try:
        return failure_loop.promote(
            query_id,
            should_answer=req.should_answer,
            expected_keyword=req.expected_keyword,
            problem_type=req.problem_type,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown failure query_id.")
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.get("/cases")
def cases():
    return failure_loop.load_cases()


@router.get("/cache")
def cache_stats():
    cache = get_shared_cache()
    return cache.stats() if cache else {"enabled": False}


@router.delete("/cache")
def clear_cache(namespace_prefix: str | None = None):
    cache = get_shared_cache()
    if not cache:
        return {"removed": 0}
    return {"removed": cache.invalidate(namespace_prefix)}
