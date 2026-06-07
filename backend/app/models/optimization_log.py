from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class OptimizationLog(Base):
    """User-recorded optimization actions (Phase 1 action log).

    Records WHAT the user did to a listing/keyword (turned off, changed title,
    price, etc.) so its effect can be reviewed against metric history later.
    """
    __tablename__ = "optimization_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    listing_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    keyword: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
