import os

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok", "groq_key_configured": bool(os.getenv("GROQ_API_KEY"))}
