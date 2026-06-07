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


def _ssl_context():
    """TLS context backed by certifi's CA bundle.

    asyncpg's ssl=True relies on the OS trust store, which is absent in a
    PyInstaller bundle → 'CERTIFICATE_VERIFY_FAILED'. Pointing at certifi's
    bundled cacert.pem makes TLS to Neon work both in dev and when frozen.
    """
    import ssl
    import certifi
    return ssl.create_default_context(cafile=certifi.where())


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
            connect_args={"ssl": _ssl_context(), "statement_cache_size": 0},
        )
        _AsyncSessionLocal = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _engine, _AsyncSessionLocal


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
