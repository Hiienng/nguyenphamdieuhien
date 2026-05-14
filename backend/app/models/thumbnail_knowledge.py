from sqlalchemy import Column, Integer, String, JSON, DateTime, UniqueConstraint, func
from ..core.database import Base


class ThumbnailKnowledge(Base):
    __tablename__ = "thumbnail_knowledge"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_type = Column(String(64), nullable=False)
    target_audience = Column(String(64), nullable=False)
    patterns = Column(JSON, nullable=False)
    # patterns structure:
    # {
    #   "dominant_colors": [...],
    #   "bg_style": "white|lifestyle|gradient|...",
    #   "text_overlay": true/false,
    #   "composition": "centered|flat_lay|...",
    #   "mood": "warm|minimal|playful|...",
    #   "common_props": [...],
    #   "ta_signals": [...],
    #   "sample_count": N
    # }
    sample_urls = Column(JSON)   # list of image_urls used
    sample_count = Column(Integer)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("product_type", "target_audience", name="uq_thumbnail_knowledge_pt_ta"),
    )
