from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
import os


_CORE_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _CORE_DIR.parents[1]
_PROJECT_DIR = _CORE_DIR.parents[2]
# ETSY_RESOURCE_ROOT is set by the desktop launcher (PyInstaller bundle dir) so
# the bundled .env is found; it takes priority over the dev-tree locations.
_RESOURCE_ROOT = os.environ.get("ETSY_RESOURCE_ROOT")
_ENV_FILES = tuple(filter(None, (
    (Path(_RESOURCE_ROOT) / ".env") if _RESOURCE_ROOT else None,
    _PROJECT_DIR / ".env",
    _BACKEND_DIR / ".env",
    Path.cwd() / ".env",
)))


class Settings(BaseSettings):
    # Database (Neon PostgreSQL) — the user's own ads data
    DATABASE_URL: str = ""

    # Claude / Anthropic
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-6"

    # JWT Auth
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MIN: int = 30
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # App
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = ""

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    @staticmethod
    def _normalize_asyncpg_url(raw: str) -> str:
        import re
        url = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        url = re.sub(r"[?&]sslmode=[^&]*", "", url)
        url = re.sub(r"[?&]ssl=[^&]*", "", url)
        url = re.sub(r"[?&]channel_binding=[^&]*", "", url)
        return url

    @property
    def async_db_url(self) -> str:
        return self._normalize_asyncpg_url(self.DATABASE_URL)

    class Config:
        env_file = _ENV_FILES
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    return s
