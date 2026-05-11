from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


_CORE_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _CORE_DIR.parents[1]
_PROJECT_DIR = _CORE_DIR.parents[2]
_ENV_FILES = (
    _PROJECT_DIR / ".env",
    _BACKEND_DIR / ".env",
    Path.cwd() / ".env",
)


class Settings(BaseSettings):
    # Database (Neon PostgreSQL) — internal data
    DATABASE_URL: str = ""
    # Market data DB (etsy_star_engine output)
    ETSY_MARKET_DB: str = ""

    # AI Vision — Gemini (primary) + HuggingFace Router (fallback)
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEY_2: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    HUGGINGFACE_API_KEY: str = ""
    # Use a router-supported vision model with an explicit provider suffix.
    HF_MODEL: str = "zai-org/GLM-4.5V"

    # ImageKit (screenshot storage)
    IMAGEKIT_PUBLIC_KEY: str = ""
    IMAGEKIT_PRIVATE_KEY: str = ""
    IMAGEKIT_URL_ENDPOINT: str = ""
    IMAGEKIT_FOLDER: str = "/listing/EtseeMate"

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

    @property
    def async_market_db_url(self) -> str:
        return self._normalize_asyncpg_url(self.ETSY_MARKET_DB or self.DATABASE_URL)

    class Config:
        env_file = _ENV_FILES
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    print(f"DEBUG: Settings loaded. Gemini Key present: {bool(s.GEMINI_API_KEY)}")
    return s
