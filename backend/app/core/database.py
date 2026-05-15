import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

engine = create_async_engine(
    settings.async_db_url,
    echo=settings.APP_ENV == "development",
    pool_size=5,
    max_overflow=10,
    # statement_cache_size=0 disables asyncpg's prepared statement cache, which
    # prevents "InvalidCachedStatementError" after DDL (CREATE/ALTER TABLE at
    # startup invalidates ALL server-side cached plans across ALL connections).
    connect_args={"ssl": True, "statement_cache_size": 0},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Second engine — market data DB (ETSY_MARKET_DB / etsy_star_engine output)
# Built lazily so env var is read at first use, not at import time.
_market_engine = None
_MarketSessionLocal = None


def _get_market_session_factory() -> async_sessionmaker:
    global _market_engine, _MarketSessionLocal
    if _MarketSessionLocal is None:
        _market_engine = create_async_engine(
            get_settings().async_market_db_url,
            echo=get_settings().APP_ENV == "development",
            pool_size=3,
            max_overflow=5,
            connect_args={"ssl": True},
        )
        _MarketSessionLocal = async_sessionmaker(
            bind=_market_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _MarketSessionLocal


class MarketSessionLocal:
    """Context manager proxy — creates engine lazily on first use."""
    def __new__(cls):
        return _get_market_session_factory()()


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_tenant_db(tenant_id: str) -> AsyncSession:
    """Yield a session with app.tenant_id set — activates RLS policies."""
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": tenant_id},
            )
            yield session
        finally:
            await session.close()


async def create_tables() -> None:
    # NOTE: ALTER TABLE migrations removed — all columns were added long ago.
    # Keeping DDL in startup causes asyncpg "InvalidCachedStatementError" because
    # PostgreSQL invalidates ALL server-side prepared plans across ALL connections
    # after any DDL statement. Use raw SQL migration scripts for new columns.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
