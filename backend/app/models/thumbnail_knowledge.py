from sqlalchemy import Column, Integer, String, JSON, Boolean, DateTime, UniqueConstraint, func, Text
from ..core.database import Base


class ThumbnailFeatures(Base):
    """Rich visual features extracted per thumbnail image."""
    __tablename__ = "thumbnail_features"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Source tracking
    source = Column(String(16), nullable=False)          # 'market' | 'user'
    listing_id = Column(String(64))                      # optional, for market listings
    image_url = Column(Text)
    product_type = Column(String(64))
    badge = Column(String(64))                           # 'Popular now' | 'Bestseller' | None
    extracted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Subject
    subject = Column(String(256))                        # e.g. "personalized onesie"
    subject_colors = Column(JSON)                        # list of hex codes
    subject_color_names = Column(JSON)                   # list of color names

    # Background
    background_color = Column(String(16))                # hex
    background_color_name = Column(String(64))
    background_type = Column(String(64))                 # 'white_studio' | 'lifestyle' | 'gradient' | etc.
    background_description = Column(Text)

    # Theme & Style
    theme = Column(String(128))                          # e.g. "minimalist gift", "holiday celebration"
    fabric_material = Column(String(128))                # e.g. "cotton", "fleece"

    # Decoration
    decoration_object = Column(String(256))              # e.g. "name Jason", "dinosaur patch"
    decoration_technique = Column(String(64))            # 'embroidery' | 'print' | 'heat_transfer' | 'none'
    decoration_colors = Column(JSON)                     # list of hex codes

    # Seasonal & Context
    seasonal_type = Column(String(64))                   # 'christmas' | 'halloween' | 'easter' | 'valentines' | 'non_seasonal'
    lifestyle_props = Column(JSON)                       # list of strings

    # Composition & Mood
    text_overlay = Column(Boolean, default=False)
    text_overlay_content = Column(Text)
    composition = Column(String(64))                     # 'centered' | 'flat_lay' | 'close_up' | 'editorial'
    overall_mood = Column(String(128))                   # e.g. "warm, playful"


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
