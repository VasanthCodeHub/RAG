from fastapi import APIRouter, HTTPException

from api import store
from api.schemas import QualitySignal, QueryRequest, QueryResponse

router = APIRouter(tags=["query"])


def _quality_signal(trace: dict) -> QualitySignal:
    rerank_step = trace["steps"]["rerank"]
    top_score = rerank_step["top_score"]
    docs_passed = sum(
        1 for d in rerank_step["documents"] if d["score"] is not None and d["score"] > 0
    )
    if top_score is None or top_score <= 0:
        label = "no_relevant_match"
    elif top_score < 2:
        label = "weak_match"
    else:
        label = "strong_match"
    return QualitySignal(
        top_rerank_score=top_score,
        docs_passed_positive_threshold=docs_passed,
        docs_returned=rerank_step["docs_after_rerank"],
        label=label,
    )


@router.post("/query", response_model=QueryResponse)
def run_query(req: QueryRequest):
    entry = store.get(req.pdf_hash)
    if not entry:
        raise HTTPException(status_code=404, detail="Unknown pdf_hash -- upload the document first.")

    response = entry["pipeline"].run(req.query)
    trace = response.trace

    return QueryResponse(
        query_id=trace["query_id"],
        query=trace["query"],
        answer=response.answer,
        reasoning=response.reasoning,
        issues=response.issues,
        status=trace["status"],
        total_duration_ms=trace["total_duration_ms"],
        steps=trace["steps"],
        contexts=response.contexts,
        quality_signal=_quality_signal(trace),
    )
