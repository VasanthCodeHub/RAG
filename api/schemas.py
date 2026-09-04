from typing import Any, Optional

from pydantic import BaseModel


class DocumentIngestResponse(BaseModel):
    pdf_hash: str
    filename: str
    n_chunks: int
    from_cache: bool
    duration_ms: float


class QueryRequest(BaseModel):
    pdf_hash: str
    query: str


class QualitySignal(BaseModel):
    top_rerank_score: Optional[float]
    docs_passed_positive_threshold: int
    docs_returned: int
    label: str


class QueryResponse(BaseModel):
    query_id: str
    query: str
    answer: str
    reasoning: Optional[str] = None
    issues: list[dict[str, Any]]
    status: str
    total_duration_ms: float
    steps: dict[str, Any]
    contexts: list[str]
    quality_signal: QualitySignal


class JudgeRequest(BaseModel):
    question: str
    contexts: list[str]
    answer: str
    groq_api_key: str


class JudgeResponse(BaseModel):
    rules: dict[str, Any]
    judge: dict[str, Any]


class RatingRequest(BaseModel):
    query_id: str
    question: str
    answer: str
    contexts: list[str]
    judge_helpfulness: Optional[int] = None
    judge_tone: Optional[int] = None
    judge_reasoning: Optional[str] = None
    human_helpfulness: int
    human_tone: int
    note: Optional[str] = None


class RatingSavedResponse(BaseModel):
    status: str
    n_ratings: int


class ApiKeyRequest(BaseModel):
    groq_api_key: str
