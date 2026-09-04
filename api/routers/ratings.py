from datetime import datetime, timezone

from fastapi import APIRouter

from api import ratings_store
from api.schemas import RatingRequest, RatingSavedResponse

router = APIRouter(tags=["ratings"])


@router.post("/ratings", response_model=RatingSavedResponse)
def save_rating(req: RatingRequest):
    record = req.model_dump()
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    n_ratings = ratings_store.append(record)
    return RatingSavedResponse(status="saved", n_ratings=n_ratings)


@router.get("/ratings")
def list_ratings():
    return ratings_store.list_all()
