import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class CreditAccount(Base):
    __tablename__ = "credit_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    # Legacy column, kept in sync = subscription_credits + topup_credits. DO NOT drop yet.
    balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # New buckets (migration 010)
    subscription_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    topup_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # When the subscription bucket should be refilled / reset (usually = subscription.period_end)
    subscription_credits_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    # +N for grant/refill/refund, -N for debit
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # tx_type: deposit / debit / trial_grant / subscription_refill / topup_5 / topup_10 / feature_debit / refund
    tx_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # Which bucket the transaction touched: "subscription" | "topup" | NULL (legacy)
    bucket: Mapped[str | None] = mapped_column(String(16), nullable=True)
    description: Mapped[str | None] = mapped_column(Text)
    stripe_pi_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
