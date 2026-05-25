from pydantic import BaseModel
from typing import Optional, List, Literal


class CheckoutResponse(BaseModel):
    checkout_url: str


class SubscriptionStatusResponse(BaseModel):
    status: str  # active / trial / cancelled / expired / none
    plan: Optional[str] = None
    period_end: Optional[str] = None
    stripe_sub_id: Optional[str] = None


class TrialStatusResponse(BaseModel):
    trial_active: bool
    days_remaining: int
    hours_remaining: int
    trial_ends_at: Optional[str] = None  # ISO datetime
    can_access_features: bool


class CreditTransaction(BaseModel):
    amount: int
    tx_type: str
    description: Optional[str]
    bucket: Optional[str] = None
    created_at: str


class CreditsResponse(BaseModel):
    # New shape (two buckets)
    subscription: int
    topup: int
    total: int
    reset_at: Optional[str] = None
    # Legacy field — kept = total for backward compat with existing FE
    balance: int
    transactions: List[CreditTransaction] = []


class PlanInfo(BaseModel):
    id: str
    name: str
    price_cents: int
    is_subscription: bool
    interval: Optional[str] = None
    duration_days: Optional[int] = None
    credits: Optional[int] = None
    credits_per_cycle: Optional[int] = None
    polar_product_id: Optional[str] = None


class TopupInfo(BaseModel):
    id: str
    price_cents: int
    credits: int
    polar_product_id: Optional[str] = None


class PlansResponse(BaseModel):
    plans: List[PlanInfo]
    topups: List[TopupInfo]


class SubscribeRequest(BaseModel):
    plan: Literal["basic_monthly"] = "basic_monthly"


class TopupRequest(BaseModel):
    pack: Literal["topup_5", "topup_10"]
