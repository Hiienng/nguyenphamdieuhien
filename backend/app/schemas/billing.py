from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CheckoutResponse(BaseModel):
    checkout_url: str


class SubscriptionStatusResponse(BaseModel):
    status: str  # active / cancelled / expired / none
    plan: Optional[str] = None
    period_end: Optional[str] = None
    stripe_sub_id: Optional[str] = None


class CreditTransaction(BaseModel):
    amount: int
    tx_type: str
    description: Optional[str]
    created_at: str


class CreditsResponse(BaseModel):
    balance: int
    transactions: List[CreditTransaction] = []
