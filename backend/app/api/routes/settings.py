"""
App settings — desktop-only.

Lets the signed-in user view/change the database connection from the in-app
Settings screen. The value is written to the per-user config file that the
desktop launcher reads on startup (~/.getifyco-listing-portal/config.env), so it
overrides the build's baked default. Changes apply after restarting the app.
"""
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...core.auth_middleware import get_current_active_user
from ...core.config import get_settings
from ...models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])

USER_CONFIG = Path.home() / ".getifyco-listing-portal" / "config.env"


class DatabaseUpdate(BaseModel):
    database_url: str


def _mask(url: str) -> str:
    """Show scheme://user@host/db without leaking the password."""
    if not url:
        return ""
    try:
        p = urlsplit(url)
        host = p.hostname or ""
        db = (p.path or "").lstrip("/")
        user = p.username or ""
        who = f"{user}@" if user else ""
        return f"{p.scheme}://{who}{host}/{db}"
    except Exception:
        return "(set)"


def _read_user_config() -> dict:
    cfg = {}
    if USER_CONFIG.exists():
        for line in USER_CONFIG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def _write_user_config(cfg: dict) -> None:
    USER_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{k}={v}" for k, v in cfg.items() if v) + "\n"
    USER_CONFIG.write_text(body, encoding="utf-8")
    try:
        USER_CONFIG.chmod(0o600)
    except Exception:
        pass


@router.get("/database")
async def get_database_settings(user: User = Depends(get_current_active_user)):
    s = get_settings()
    return {
        "database_url_masked": _mask(s.DATABASE_URL),
        "config_path": str(USER_CONFIG),
    }


@router.post("/database")
async def update_database_settings(
    body: DatabaseUpdate,
    user: User = Depends(get_current_active_user),
):
    db_url = body.database_url.strip()
    if not db_url.startswith(("postgres://", "postgresql://", "postgresql+asyncpg://")):
        raise HTTPException(400, "Database URL không hợp lệ (phải là chuỗi postgres://...).")

    cfg = _read_user_config()
    cfg["DATABASE_URL"] = db_url
    # Preserve the existing token so the launcher still considers the app configured.
    if "SECRET_KEY" not in cfg and get_settings().SECRET_KEY:
        cfg["SECRET_KEY"] = get_settings().SECRET_KEY

    _write_user_config(cfg)
    return {"ok": True, "restart_required": True, "database_url_masked": _mask(db_url)}
