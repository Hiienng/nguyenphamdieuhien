from fastapi import APIRouter, HTTPException, Response, Depends

from ...core.auth_middleware import get_current_active_user
from ...core.config import get_settings
from ...models.user import User
from ...schemas.auth import LoginRequest, TokenResponse, MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Single-user login: the shared SECRET_KEY is the access token."""
    secret = get_settings().SECRET_KEY
    if not secret or body.token != secret:
        raise HTTPException(status_code=401, detail="Invalid access token")
    return TokenResponse(access_token=secret)


@router.post("/logout")
async def logout(response: Response):
    # Token is held client-side; nothing to revoke server-side.
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_active_user)):
    return MeResponse(id=user.id, email=user.email, is_admin=user.is_admin)
