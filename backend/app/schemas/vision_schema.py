from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Knowledge Generation
# ---------------------------------------------------------------------------

class KnowledgeGenerateRequest(BaseModel):
    product_type: str
    top_n: int = 20


class KnowledgeRecord(BaseModel):
    id: int
    product_type: str
    target_audience: str
    patterns: dict[str, Any]
    sample_urls: list[str] | None = None
    sample_count: int | None = None
    generated_at: datetime | None = None

    model_config = {"from_attributes": True}


class KnowledgeListResponse(BaseModel):
    items: list[KnowledgeRecord]
    total: int


# ---------------------------------------------------------------------------
# Thumbnail Evaluation
# ---------------------------------------------------------------------------

class CriterionScore(BaseModel):
    score: float = Field(..., ge=1, le=10, description="Score from 1 to 10")
    comment: str


class ThumbnailEvalResponse(BaseModel):
    product_type: str
    target_audience: str
    overall: float = Field(..., ge=1, le=10)
    scores: dict[str, CriterionScore]
    strengths: list[str]
    suggestions: list[str]
