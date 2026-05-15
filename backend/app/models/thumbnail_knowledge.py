from sqlalchemy import Column, Integer, SmallInteger, String, JSON, Boolean, DateTime, UniqueConstraint, func, Text
from ..core.database import Base


class ThumbnailFeatures(Base):
    """Rich visual features extracted per thumbnail image."""
    __tablename__ = "thumbnail_features"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Source tracking
    source = Column(String(16), nullable=False)
    listing_id = Column(String(64))
    image_url = Column(Text)
    product_type = Column(String(64))
    badge = Column(String(64))
    extracted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Subject
    subject = Column(String(256))
    subject_colors = Column(JSON)
    subject_color_names = Column(JSON)

    # Background
    background_color = Column(String(16))
    background_color_name = Column(String(64))
    background_type = Column(String(64))
    background_description = Column(Text)

    # Theme & Style
    theme = Column(String(128))
    fabric_material = Column(String(128))

    # Decoration
    decoration_object = Column(String(256))
    decoration_technique = Column(String(64))
    decoration_colors = Column(JSON)

    # Seasonal & Context
    seasonal_type = Column(String(64))
    lifestyle_props = Column(JSON)

    # Composition & Mood
    text_overlay = Column(Boolean, default=False)
    text_overlay_content = Column(Text)
    composition = Column(String(64))
    overall_mood = Column(String(128))

    # Visual quality
    image_brightness = Column(String(16))        # dark|medium|bright
    image_contrast = Column(String(16))          # low|medium|high
    color_harmony = Column(String(32))           # monochromatic|analogous|complementary|triadic|neutral
    color_count = Column(SmallInteger)           # number of dominant colors 1-5+
    background_clutter = Column(String(16))      # clean|minimal|moderate|busy

    # Product presentation
    product_visibility = Column(String(32))      # full|partial|close_up|multiple_angles
    product_size_in_frame = Column(String(16))   # small|medium|large|fills_frame
    personalization_visible = Column(Boolean, default=False)
    gift_cue_visible = Column(Boolean, default=False)
    size_reference = Column(Boolean, default=False)

    # Audience & occasion signals
    gender_signal = Column(String(16))           # neutral|feminine|masculine
    age_target = Column(String(16))              # newborn|infant|toddler|adult|unknown
    occasion_signal = Column(String(32))         # everyday|gift|seasonal|hospital|announcement
    style_aesthetic = Column(String(32))         # modern|rustic|boho|classic|whimsical|minimal

    # ML label: 1=Bestseller/Popular now, 0=other, NULL=user upload
    ml_label = Column(SmallInteger)


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
