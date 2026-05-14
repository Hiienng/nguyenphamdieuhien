from pydantic import BaseModel, EmailStr
from typing import Optional


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SubscriptionInfo(BaseModel):
    status: str
    period_end: Optional[str] = None


class MeResponse(BaseModel):
    id: str
    email: str
    is_admin: bool
    subscription: Optional[SubscriptionInfo] = None
    credit_balance: int = 0
