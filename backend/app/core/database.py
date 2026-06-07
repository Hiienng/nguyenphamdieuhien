import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .config import get_settings

logger = logging.getLogger(__name__)

# ── Lazy engine init ─────────────────────────────────────────────────────────
# Engines are created on first use so that a missing/empty DATABASE_URL at
# import time does not crash the process before uvicorn can bind the port.

_engine = None
_AsyncSessionLocal = None
_market_engine = None
_MarketSessionLocal = None


def _get_engine():
    global _engine, _AsyncSessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.async_db_url,
            echo=settings.APP_ENV == "development",
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"ssl": True, "statement_cache_size": 0},
        )
        _AsyncSessionLocal = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _engine, _AsyncSessionLocal


def _get_market_session_factory() -> async_sessionmaker:
    global _market_engine, _MarketSessionLocal
    if _MarketSessionLocal is None:
        settings = get_settings()
        _market_engine = create_async_engine(
            settings.async_market_db_url,
            echo=settings.APP_ENV == "development",
            pool_size=3,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"ssl": True},
        )
        _MarketSessionLocal = async_sessionmaker(
            bind=_market_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _MarketSessionLocal


# ── Compatibility shims ───────────────────────────────────────────────────────
# Code throughout the app does `from .database import engine, AsyncSessionLocal`.
# These proxy objects forward attribute access to the lazy-initialised instances.

class _EngineProxy:
    def __getattr__(self, name):
        return getattr(_get_engine()[0], name)
    def begin(self):
        return _get_engine()[0].begin()
    def connect(self):
        return _get_engine()[0].connect()

class _SessionLocalProxy:
    def __call__(self, *a, **kw):
        return _get_engine()[1](*a, **kw)
    def __getattr__(self, name):
        return getattr(_get_engine()[1], name)

engine = _EngineProxy()
AsyncSessionLocal = _SessionLocalProxy()


class MarketSessionLocal:
    """Context manager proxy — creates engine lazily on first use."""
    def __new__(cls):
        return _get_market_session_factory()()


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    _, factory = _get_engine()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_tenant_db(tenant_id: str) -> AsyncSession:
    """Yield a session with app.tenant_id set — activates RLS policies."""
    _, factory = _get_engine()
    async with factory() as session:
        try:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": tenant_id},
            )
            yield session
        finally:
            await session.close()


async def create_tables() -> None:
    eng, _ = _get_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
