from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Rich Thumbnail Feature Extraction
# ---------------------------------------------------------------------------

class ThumbnailFeatures(BaseModel):
    """Rich visual features extracted from a single thumbnail image."""
    # Source
    source: str = "user"          # 'market' | 'user'
    listing_id: str | None = None
    image_url: str | None = None
    product_type: str | None = None
    badge: str | None = None

    # Subject
    subject: str | None = None
    subject_colors: list[str] = Field(default_factory=list)       # hex codes
    subject_color_names: list[str] = Field(default_factory=list)  # color names

    # Background
    background_color: str | None = None        # hex
    background_color_name: str | None = None
    background_type: str | None = None         # white_studio | lifestyle | gradient | texture | outdoor
    background_description: str | None = None

    # Theme & Style
    theme: str | None = None
    fabric_material: str | None = None

    # Decoration
    decoration_object: str | None = None
    decoration_technique: str | None = None    # embroidery | print | heat_transfer | none
    decoration_colors: list[str] = Field(default_factory=list)

    # Seasonal & Context
    seasonal_type: str | None = None           # christmas | halloween | easter | valentines | non_seasonal
    lifestyle_props: list[str] = Field(default_factory=list)

    # Composition & Mood
    text_overlay: bool = False
    text_overlay_content: str | None = None
    composition: str | None = None
    overall_mood: str | None = None

    # Visual quality
    image_brightness: str | None = None        # dark|medium|bright
    image_contrast: str | None = None          # low|medium|high
    color_harmony: str | None = None           # monochromatic|analogous|complementary|triadic|neutral
    color_count: int | None = None
    background_clutter: str | None = None      # clean|minimal|moderate|busy

    # Product presentation
    product_visibility: str | None = None      # full|partial|close_up|multiple_angles
    product_size_in_frame: str | None = None   # small|medium|large|fills_frame
    personalization_visible: bool = False
    gift_cue_visible: bool = False
    size_reference: bool = False

    # Audience & occasion signals
    gender_signal: str | None = None           # neutral|feminine|masculine
    age_target: str | None = None              # newborn|infant|toddler|adult|unknown
    occasion_signal: str | None = None         # everyday|gift|seasonal|hospital|announcement
    style_aesthetic: str | None = None         # modern|rustic|boho|classic|whimsical|minimal

    ml_label: int | None = None

    model_config = {"from_attributes": True}


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
    features: ThumbnailFeatures | None = None
    ml_score: float | None = None       # LightGBM proba(1), 0–1, None if model not available
