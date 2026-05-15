from datetime import datetime
from sqlalchemy import Numeric, Text, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class ThresholdConfig(Base):
    __tablename__ = "threshold_configs"

    id:         Mapped[int]      = mapped_column(primary_key=True, autoincrement=True)
    roas_be:    Mapped[float]    = mapped_column(Numeric(5, 2), nullable=False)  # ROAS huề vốn
    cr_high:    Mapped[float]    = mapped_column(Numeric(5, 2), nullable=False)  # CR cao ≥ X%
    ctr_high:   Mapped[float]    = mapped_column(Numeric(5, 2), nullable=False)  # CTR cao ≥ X%
    note:       Mapped[str|None] = mapped_column(Text)
    created_by: Mapped[str]      = mapped_column(Text, nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True)
