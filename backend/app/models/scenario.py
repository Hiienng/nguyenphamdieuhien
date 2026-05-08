from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class ScenarioRule(Base):
    __tablename__ = "scenarios_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    roas_band: Mapped[str] = mapped_column(String(32), nullable=False)
    cr_level: Mapped[str] = mapped_column(String(8), nullable=False)
    ctr_level: Mapped[str] = mapped_column(String(8), nullable=False)
    case_name: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    cause: Mapped[str | None] = mapped_column(Text)
    fix_listing: Mapped[str | None] = mapped_column(Text)
    fix_ads: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now()
    )
