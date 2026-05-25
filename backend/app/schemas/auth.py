from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserInfo(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    created_at: Optional[str] = None
    onboarding_completed: Optional[bool] = False
    product_categories: Optional[List[str]] = None
    seller_location: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class SubscriptionInfo(BaseModel):
    status: str
    period_end: Optional[str] = None


class MeResponse(BaseModel):
    id: str
    email: str
    is_admin: bool
    subscription: Optional[SubscriptionInfo] = None
    credit_balance: int = 0
    onboarding_completed: Optional[bool] = False
    product_categories: Optional[List[str]] = None
    seller_location: Optional[str] = None


# Onboarding Schemas
class ProductCategory(BaseModel):
    id: str
    name: str
    label: str


class OnboardingSetupRequest(BaseModel):
    product_categories: List[str]
    seller_location: str

    @field_validator("product_categories")
    @classmethod
    def validate_categories_count(cls, v: List[str]) -> List[str]:
        if not (1 <= len(v) <= 3):
            raise ValueError("product_categories must have 1-3 items")
        return v


class OnboardingSetupResponse(BaseModel):
    success: bool
    user: UserInfo
