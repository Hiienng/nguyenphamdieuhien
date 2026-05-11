"""
Crawler operations layer.

Two tables:
    crawl_run    — append-only ledger of every crawler job invocation.
    crawl_queue  — pending listings for internal_listing_crawler (Flow 2).

Used by:
    - market_engine_crawler/run_scheduled.py (writes crawl_run via Python sync helpers)
    - internal_service.confirm_import        (enqueues new listings)
    - FE Operations card                     (reads via /api/v1/ops/*)

The crawler scripts run on a separate Mac and write directly to Neon — they
import `crawler_ops_sync` (a sync mirror) over the same DATABASE_URL.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


_DDL = [
    """
    CREATE TABLE IF NOT EXISTS crawl_run (
        id            SERIAL PRIMARY KEY,
        job_name      VARCHAR(64) NOT NULL,
        started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        finished_at   TIMESTAMPTZ,
        status        VARCHAR(16) NOT NULL DEFAULT 'running',
        target_count  INTEGER,
        success_count INTEGER,
        fail_count    INTEGER,
        error_summary TEXT,
        host          VARCHAR(64),
        metadata      JSONB
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_crawl_run_job_started ON crawl_run (job_name, started_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS crawl_queue (
        listing_id   VARCHAR(32) PRIMARY KEY,
        queued_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        last_attempt TIMESTAMPTZ,
        attempts     INTEGER NOT NULL DEFAULT 0,
        next_after   TIMESTAMPTZ DEFAULT now(),
        reason       VARCHAR(32),
        status       VARCHAR(16) NOT NULL DEFAULT 'pending'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_crawl_queue_status_next ON crawl_queue (status, next_after)",
]


async def ensure_crawler_tables(db: AsyncSession) -> None:
    for stmt in _DDL:
        await db.execute(text(stmt))
    await db.commit()


async def enqueue_listings(db: AsyncSession, listing_ids: list[str], reason: str = "new_listing") -> int:
    """Insert listing_ids into crawl_queue, ignore duplicates. Returns rows inserted."""
    if not listing_ids:
        return 0
    result = await db.execute(
        text("""
            INSERT INTO crawl_queue (listing_id, reason)
            SELECT unnest(:ids), :reason
            ON CONFLICT (listing_id) DO NOTHING
        """),
        {"ids": listing_ids, "reason": reason},
    )
    await db.commit()
    return result.rowcount or 0


async def list_recent_runs(db: AsyncSession, limit: int = 20, job_name: str | None = None) -> list[dict]:
    sql = "SELECT * FROM crawl_run"
    params: dict = {"limit": limit}
    if job_name:
        sql += " WHERE job_name = :j"
        params["j"] = job_name
    sql += " ORDER BY started_at DESC LIMIT :limit"
    rows = (await db.execute(text(sql), params)).mappings().all()
    return [dict(r) for r in rows]


async def queue_summary(db: AsyncSession) -> dict:
    row = (await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'pending') AS pending,
            COUNT(*) FILTER (WHERE status = 'done')    AS done,
            COUNT(*) FILTER (WHERE status = 'failed')  AS failed
        FROM crawl_queue
    """))).mappings().one()
    return dict(row)
