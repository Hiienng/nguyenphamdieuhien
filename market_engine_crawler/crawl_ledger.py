"""
Sync helper for crawler scripts running on the crawler-Mac.

Reads DATABASE_URL from env (use the same Neon URL as backend), opens a sync
psycopg connection, and writes to `crawl_run` / `crawl_queue`.

Usage (in any crawler script):

    from crawl_ledger import start_run, finish_run, fetch_pending_queue, mark_queue_done

    run_id = start_run("market_discovery", target_count=30, metadata={"vm": "VM01"})
    try:
        # ... crawl ...
        finish_run(run_id, "success", success_count=28, fail_count=2)
    except Exception as e:
        finish_run(run_id, "failed", error_summary=str(e))
        raise
"""
from __future__ import annotations

import json
import os
import socket
from datetime import datetime
from typing import Any

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


def _conn():
    if psycopg is None:
        raise RuntimeError("psycopg3 not installed — pip install 'psycopg[binary]'")
    url = os.getenv("DATABASE_URL") or os.getenv("ASYNC_DB_URL", "").replace("+asyncpg", "")
    if not url:
        raise RuntimeError("DATABASE_URL env var not set")
    # asyncpg DSN uses postgresql+asyncpg:// — strip the driver suffix for psycopg
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return psycopg.connect(url, autocommit=True)


def start_run(job_name: str, *, target_count: int | None = None, metadata: dict | None = None) -> int:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """
            INSERT INTO crawl_run (job_name, target_count, host, metadata, status)
            VALUES (%s, %s, %s, %s::jsonb, 'running')
            RETURNING id
            """,
            (job_name, target_count, socket.gethostname(), json.dumps(metadata or {})),
        )
        return cur.fetchone()[0]


def finish_run(
    run_id: int,
    status: str,
    *,
    success_count: int | None = None,
    fail_count: int | None = None,
    error_summary: str | None = None,
) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """
            UPDATE crawl_run
            SET finished_at = now(),
                status = %s,
                success_count = COALESCE(%s, success_count),
                fail_count = COALESCE(%s, fail_count),
                error_summary = %s
            WHERE id = %s
            """,
            (status, success_count, fail_count, error_summary, run_id),
        )


# ── crawl_queue helpers (Flow 2: internal_listing_crawler) ────────────────

def fetch_pending_queue(limit: int = 20) -> list[tuple[str, int]]:
    """Pop up to `limit` listing_ids whose next_after has passed. Returns
    list of (listing_id, attempts). Caller must mark them done/failed."""
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT listing_id, attempts
            FROM crawl_queue
            WHERE status = 'pending' AND next_after <= now()
            ORDER BY queued_at ASC
            LIMIT %s
            """,
            (limit,),
        )
        return list(cur.fetchall())


def mark_queue_done(listing_id: str) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """
            UPDATE crawl_queue
            SET status = 'done', last_attempt = now()
            WHERE listing_id = %s
            """,
            (listing_id,),
        )


def mark_queue_failed(listing_id: str, attempts: int) -> None:
    """Exponential backoff: next_after = now() + 1h * 2^attempts (cap 24h)."""
    backoff_hours = min(24, 2 ** attempts)
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """
            UPDATE crawl_queue
            SET attempts = attempts + 1,
                last_attempt = now(),
                next_after = now() + (%s || ' hours')::interval,
                status = CASE WHEN attempts + 1 >= 5 THEN 'failed' ELSE 'pending' END
            WHERE listing_id = %s
            """,
            (backoff_hours, listing_id),
        )
