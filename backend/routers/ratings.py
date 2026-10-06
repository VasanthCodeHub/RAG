from datetime import datetime, timezone

from fastapi import APIRouter

from backend import ratings_store
from observability import metrics as observability
from backend.schemas import RatingRequest, RatingSavedResponse

router = APIRouter(tags=["ratings"])


@router.post("/ratings", response_model=RatingSavedResponse)
def save_rating(req: RatingRequest):
    record = req.model_dump()
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    n_ratings = ratings_store.append(record)
    # A low human score is a failure the automatic checks missed: log it so
    # it can be promoted into a regression case.
    if min(req.human_helpfulness, req.human_tone) <= 2:
        logged = observability.find_query(req.query_id) or {}
        observability.record_failure(
            req.query_id,
            "low_rating",
            query=req.question,
            answer=req.answer,
            pdf_hash=logged.get("pdf_hash"),
            detail=f"helpfulness={req.human_helpfulness} tone={req.human_tone} note={req.note!r}",
        )
    return RatingSavedResponse(status="saved", n_ratings=n_ratings)


@router.get("/ratings")
def list_ratings():
    return ratings_store.list_all()
