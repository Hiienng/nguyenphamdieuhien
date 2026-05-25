"""
Reporting ETL — Materialized reporting layer for Listing Improvement.

Pipeline:
    Ingestion (raw, dup, zero-rows)  →  fn_rebuild_reporting()  →  Reporting tables
       listing_report                   GROUP BY + MAX            listings_int_ext
       manual_listing_report            compute cpc/cpp           listings_int_hist
       keyword_report                   enrich market + scenario  keywords
       manual_keyword_report

Trigger points:
    - POST /api/v1/performance/refresh  (user click "Tải lại")
    - POST /api/v1/EtseeMate/confirm     (auto after a manual import lands)

Concurrency:
    - PG advisory lock (key = 0x4953524C — "ISRL") prevents two rebuilds in parallel.
    - Ingest signature (max import_time across raw tables) debounces no-op refreshes.
"""
from __future__ import annotations

import hashlib
import time
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Thresholds (mirror performance_service constants)
CTR_THRESHOLD = 1.5
CR_THRESHOLD = 3.0
ROAS_BREAKEVEN = 2.0

_ADVISORY_LOCK_KEY = 0x4953524C  # 'ISRL'


# ─────────────────────────────────────────────────────────────────────────────
# DDL — idempotent. Called at startup.
# ─────────────────────────────────────────────────────────────────────────────

_DDL = [
    # Range-period overview, one row per (tenant_id, listing_id, period).
    """
    CREATE TABLE IF NOT EXISTS listings_int_ext (
        tenant_id       VARCHAR(36) NOT NULL,
        listing_id      VARCHAR(32) NOT NULL,
        period          VARCHAR(32) NOT NULL,
        reference_date  TIMESTAMPTZ,
        title           TEXT,
        no_vm           VARCHAR(16),
        product         VARCHAR(64),
        url             TEXT,
        views           INTEGER,
        clicks          INTEGER,
        orders          INTEGER,
        revenue         NUMERIC(12,2),
        spend           NUMERIC(12,2),
        roas            NUMERIC(8,2),
        ctr             NUMERIC(6,2),
        cr              NUMERIC(6,2),
        cpc             NUMERIC(10,2),
        cpp             NUMERIC(10,2),
        roas_band       VARCHAR(16),
        cr_level        VARCHAR(8),
        ctr_level       VARCHAR(8),
        scenario_action TEXT,
        scenario_label  TEXT,
        scenario_cause  TEXT,
        scenario_fix_listing TEXT,
        scenario_fix_ads     TEXT,
        price           INTEGER,
        discount_price  INTEGER,
        rating          REAL,
        review_count    INTEGER,
        badge           TEXT,
        free_shipping   BOOLEAN,
        is_ad           BOOLEAN,
        tag_ranking     INTEGER,
        rebuilt_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (tenant_id, listing_id, period)
    )
    """,
    # Daily history rows, one per (tenant_id, listing_id, period=YYYY-MM-DD).
    """
    CREATE TABLE IF NOT EXISTS listings_int_hist (
        tenant_id       VARCHAR(36) NOT NULL,
        listing_id      VARCHAR(32) NOT NULL,
        period          VARCHAR(32) NOT NULL,
        reference_date  TIMESTAMPTZ,
        views           INTEGER,
        clicks          INTEGER,
        orders          INTEGER,
        revenue         NUMERIC(12,2),
        spend           NUMERIC(12,2),
        roas            NUMERIC(8,2),
        cpc             NUMERIC(10,2),
        cpp             NUMERIC(10,2),
        source          VARCHAR(16),
        rebuilt_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (tenant_id, listing_id, period)
    )
    """,
    # Keyword sub-table — latest import per (tenant_id, listing_id).
    """
    CREATE TABLE IF NOT EXISTS keywords (
        tenant_id        VARCHAR(36) NOT NULL,
        listing_id       VARCHAR(32) NOT NULL,
        keyword          TEXT NOT NULL,
        period           VARCHAR(32) NOT NULL,
        currently_status VARCHAR(8),
        views            INTEGER,
        clicks           INTEGER,
        orders           INTEGER,
        revenue          NUMERIC(12,2),
        spend            NUMERIC(12,2),
        roas             NUMERIC(8,2),
        click_rate       VARCHAR(8),
        cpc              NUMERIC(10,2),
        cpp              NUMERIC(10,2),
        rebuilt_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (tenant_id, listing_id, keyword, period)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS refresh_state (
        id               INTEGER PRIMARY KEY DEFAULT 1,
        last_refresh_at  TIMESTAMPTZ,
        ingest_signature TEXT,
        duration_ms      INTEGER,
        row_counts       JSONB,
        CONSTRAINT refresh_state_singleton CHECK (id = 1)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_listings_int_ext_tenant ON listings_int_ext (tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_listings_int_hist_tenant ON listings_int_hist (tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_keywords_tenant ON keywords (tenant_id)",
]


async def ensure_reporting_tables(db: AsyncSession) -> None:
    for stmt in _DDL:
        await db.execute(text(stmt))
    await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Ingest signature — short hash over MAX(import_time) of every raw source.
# Used to skip rebuilds when nothing upstream changed.
# ─────────────────────────────────────────────────────────────────────────────

_SIGNATURE_SQL = text("""
    SELECT
        (SELECT COALESCE(MAX(import_time)::text, '') FROM listing_report)        AS lr,
        (SELECT COALESCE(MAX(import_time)::text, '') FROM manual_listing_report) AS mlr,
        (SELECT COALESCE(MAX(import_time)::text, '') FROM keyword_report)        AS kr,
        (SELECT COALESCE(MAX(import_time)::text, '') FROM manual_keyword_report) AS mkr,
        (SELECT COALESCE(MAX(refreshed_at)::text, '') FROM references_engine)    AS refs
""")


async def compute_ingest_signature(db: AsyncSession) -> str:
    row = (await db.execute(_SIGNATURE_SQL)).mappings().one()
    payload = "|".join(row[k] or "" for k in ("lr", "mlr", "kr", "mkr", "refs"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


async def get_state(db: AsyncSession) -> dict | None:
    row = (await db.execute(text(
        "SELECT last_refresh_at, ingest_signature, duration_ms, row_counts FROM refresh_state WHERE id = 1"
    ))).mappings().first()
    return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# ETL — fully rebuild reporting tables from raw.
#
# Dedup strategy (per data-desc-intdb.md §2.2):
#   manual_listing_report has duplicate rows per (listing_id, period) where some
#   columns are 0 in one row and have value in another. Use MAX per metric, NOT
#   DISTINCT ON import_time DESC — the latest row may be the zero-filled one.
# ─────────────────────────────────────────────────────────────────────────────

_INSERT_HIST_SQL = text(f"""
    INSERT INTO listings_int_hist (
        tenant_id, listing_id, period, reference_date,
        views, clicks, orders, revenue, spend, roas,
        cpc, cpp, source
    )
    WITH unioned AS (
        SELECT
            tenant_id, listing_id, period,
            import_time   AS reference_date,
            COALESCE(views, 0)   AS views,
            COALESCE(clicks, 0)  AS clicks,
            COALESCE(orders, 0)  AS orders,
            COALESCE(revenue, 0) AS revenue,
            COALESCE(spend, 0)   AS spend,
            COALESCE(roas, 0)    AS roas,
            'spy'::text AS source
        FROM listing_report
        WHERE period ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$'
          AND tenant_id = :tenant_id
        UNION ALL
        SELECT
            tenant_id, listing_id, period,
            import_time   AS reference_date,
            COALESCE(views, 0)   AS views,
            COALESCE(clicks, 0)  AS clicks,
            COALESCE(orders, 0)  AS orders,
            COALESCE(revenue, 0) AS revenue,
            COALESCE(spend, 0)   AS spend,
            COALESCE(roas, 0)    AS roas,
            'manual'::text AS source
        FROM manual_listing_report
        WHERE period ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$'
          AND tenant_id = :tenant_id
    ),
    grouped AS (
        SELECT
            tenant_id,
            listing_id,
            period,
            MAX(reference_date) AS reference_date,
            MAX(views)          AS views,
            MAX(clicks)         AS clicks,
            MAX(orders)         AS orders,
            MAX(revenue)        AS revenue,
            MAX(spend)          AS spend,
            MAX(roas)           AS roas,
            -- Prefer manual source if present (latest-corrected by user)
            (ARRAY_AGG(source ORDER BY CASE WHEN source = 'manual' THEN 0 ELSE 1 END))[1] AS source
        FROM unioned
        GROUP BY tenant_id, listing_id, period
    )
    SELECT
        tenant_id, listing_id, period, reference_date,
        views, clicks, orders, revenue, spend, roas,
        CASE WHEN clicks > 0 THEN ROUND(spend::numeric / clicks, 2) ELSE NULL END AS cpc,
        CASE WHEN orders > 0 THEN ROUND(spend::numeric / orders, 2) ELSE NULL END AS cpp,
        source
    FROM grouped
""")


_INSERT_EXT_SQL = text(f"""
    INSERT INTO listings_int_ext (
        tenant_id, listing_id, period, reference_date,
        title, no_vm, product, url,
        views, clicks, orders, revenue, spend, roas,
        ctr, cr, cpc, cpp,
        roas_band, cr_level, ctr_level,
        scenario_action, scenario_label, scenario_cause,
        scenario_fix_listing, scenario_fix_ads
    )
    WITH unioned AS (
        SELECT
            tenant_id, listing_id, title, no_vm, category AS product, period,
            import_time AS reference_date,
            COALESCE(views, 0) AS views, COALESCE(clicks, 0) AS clicks,
            COALESCE(orders, 0) AS orders, COALESCE(revenue, 0) AS revenue,
            COALESCE(spend, 0) AS spend, COALESCE(roas, 0) AS roas,
            'spy'::text AS source
        FROM listing_report
        WHERE period ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}/\\d{{4}}-\\d{{2}}-\\d{{2}}$'
          AND tenant_id = :tenant_id
        UNION ALL
        SELECT
            tenant_id, listing_id, title, no_vm, category AS product, period,
            import_time AS reference_date,
            COALESCE(views, 0) AS views, COALESCE(clicks, 0) AS clicks,
            COALESCE(orders, 0) AS orders, COALESCE(revenue, 0) AS revenue,
            COALESCE(spend, 0) AS spend, COALESCE(roas, 0) AS roas,
            'manual'::text AS source
        FROM manual_listing_report
        WHERE period ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}/\\d{{4}}-\\d{{2}}-\\d{{2}}$'
          AND tenant_id = :tenant_id
    ),
    grouped AS (
        SELECT
            tenant_id, listing_id, period,
            MAX(NULLIF(title, ''))        AS title,
            MAX(NULLIF(no_vm, ''))        AS no_vm,
            MAX(NULLIF(product, ''))      AS product,
            MAX(reference_date)           AS reference_date,
            MAX(views)   AS views,
            MAX(clicks)  AS clicks,
            MAX(orders)  AS orders,
            MAX(revenue) AS revenue,
            MAX(spend)   AS spend,
            MAX(roas)    AS roas
        FROM unioned
        GROUP BY tenant_id, listing_id, period
    ),
    enriched AS (
        SELECT
            g.*,
            CASE WHEN g.views > 0
                 THEN ROUND(g.clicks::numeric / g.views * 100, 2) ELSE 0 END AS ctr,
            CASE WHEN g.clicks > 0
                 THEN ROUND(g.orders::numeric / g.clicks * 100, 2) ELSE 0 END AS cr,
            CASE WHEN g.clicks > 0
                 THEN ROUND(g.spend::numeric / g.clicks, 2) ELSE NULL END AS cpc,
            CASE WHEN g.orders > 0
                 THEN ROUND(g.spend::numeric / g.orders, 2) ELSE NULL END AS cpp,
            CASE
                WHEN g.orders = 0                THEN 'no_sales'
                WHEN g.roas  >= {ROAS_BREAKEVEN} THEN 'profitable'
                WHEN g.roas  >= 1                THEN 'slight_loss'
                ELSE 'heavy_loss'
            END AS roas_band,
            CASE
                WHEN g.orders = 0 THEN 'zero'
                WHEN g.clicks > 0 AND (g.orders::numeric / g.clicks * 100) >= {CR_THRESHOLD}
                    THEN 'high'
                ELSE 'low'
            END AS cr_level,
            CASE
                WHEN g.views > 0 AND (g.clicks::numeric / g.views * 100) >= {CTR_THRESHOLD}
                    THEN 'high'
                ELSE 'low'
            END AS ctr_level
        FROM grouped g
    )
    SELECT
        e.tenant_id, e.listing_id, e.period, e.reference_date,
        COALESCE(e.title, l.title)                                AS title,
        COALESCE(e.no_vm, l.no_vm)                                AS no_vm,
        COALESCE(e.product, l.category)                           AS product,
        COALESCE(l.url, 'https://www.etsy.com/listing/' || e.listing_id) AS url,
        e.views, e.clicks, e.orders, e.revenue, e.spend, e.roas,
        e.ctr, e.cr, e.cpc, e.cpp,
        e.roas_band, e.cr_level, e.ctr_level,
        sr.action      AS scenario_action,
        sr.case_name   AS scenario_label,
        sr.cause       AS scenario_cause,
        sr.fix_listing AS scenario_fix_listing,
        sr.fix_ads     AS scenario_fix_ads
    FROM enriched e
    LEFT JOIN listings l ON l.listing_id = e.listing_id
    LEFT JOIN scenarios_rules sr
        ON  sr.roas_band = e.roas_band
        AND sr.cr_level  = e.cr_level
        AND sr.ctr_level = e.ctr_level
""")


# Keyword pipeline — same MAX-per-column dedup, plus cpc/cpp computation.
# Only the latest import_time per listing is retained (matches old behavior).
_INSERT_KEYWORDS_SQL = text("""
    INSERT INTO keywords (
        tenant_id, listing_id, keyword, period, currently_status,
        views, clicks, orders, revenue, spend, roas,
        click_rate, cpc, cpp
    )
    WITH unioned AS (
        SELECT
            tenant_id, listing_id, keyword, period,
            relevant   AS currently_status,
            click_rate,
            import_time,
            COALESCE(views, 0)   AS views,
            COALESCE(clicks, 0)  AS clicks,
            COALESCE(orders, 0)  AS orders,
            COALESCE(revenue, 0) AS revenue,
            COALESCE(spend, 0)   AS spend,
            COALESCE(roas, 0)    AS roas,
            0 AS source_priority
        FROM keyword_report
        WHERE tenant_id = :tenant_id
        UNION ALL
        SELECT
            tenant_id, listing_id, keyword, period,
            relevant   AS currently_status,
            click_rate,
            import_time,
            COALESCE(views, 0)   AS views,
            COALESCE(clicks, 0)  AS clicks,
            COALESCE(orders, 0)  AS orders,
            COALESCE(revenue, 0) AS revenue,
            COALESCE(spend, 0)   AS spend,
            COALESCE(roas, 0)    AS roas,
            1 AS source_priority
        FROM manual_keyword_report
        WHERE tenant_id = :tenant_id
    ),
    -- Keep only rows belonging to the latest period per (tenant_id, listing_id).
    latest_period AS (
        SELECT tenant_id, listing_id, MAX(period) AS latest_period
        FROM unioned
        WHERE period IS NOT NULL AND period <> '' AND period <> 'custom_default'
        GROUP BY tenant_id, listing_id
    ),
    latest AS (
        SELECT u.tenant_id, u.listing_id, MAX(u.import_time) AS latest_import_time
        FROM unioned u
        JOIN latest_period lp
          ON lp.tenant_id  = u.tenant_id
         AND lp.listing_id = u.listing_id
         AND lp.latest_period = u.period
        GROUP BY u.tenant_id, u.listing_id
    ),
    filtered AS (
        SELECT u.*
        FROM unioned u
        JOIN latest_period lp
          ON lp.tenant_id  = u.tenant_id
         AND lp.listing_id = u.listing_id
         AND lp.latest_period = u.period
        JOIN latest l
          ON l.tenant_id  = u.tenant_id
         AND l.listing_id = u.listing_id
         AND l.latest_import_time = u.import_time
    ),
    grouped AS (
        SELECT
            tenant_id, listing_id, keyword, period,
            (ARRAY_AGG(currently_status ORDER BY source_priority DESC))[1] AS currently_status,
            (ARRAY_AGG(click_rate        ORDER BY source_priority DESC))[1] AS click_rate,
            MAX(views)   AS views,
            MAX(clicks)  AS clicks,
            MAX(orders)  AS orders,
            MAX(revenue) AS revenue,
            MAX(spend)   AS spend,
            MAX(roas)    AS roas
        FROM filtered
        GROUP BY tenant_id, listing_id, keyword, period
    )
    SELECT
        tenant_id, listing_id, keyword, period, currently_status,
        views, clicks, orders, revenue, spend, roas,
        click_rate,
        CASE WHEN clicks > 0 THEN ROUND(spend::numeric / clicks, 2) ELSE NULL END AS cpc,
        CASE WHEN orders > 0 THEN ROUND(spend::numeric / orders, 2) ELSE NULL END AS cpp
    FROM grouped
""")


async def rebuild_reporting(db: AsyncSession, tenant_id: str) -> dict:
    """Full rebuild of reporting tables for a single tenant. EtseeMate data only —
    market enrichment (price/rating/...) happens at serving time via market_db."""
    t0 = time.monotonic()

    # Per-tenant advisory lock key: XOR base key with hash of tenant_id so
    # different tenants can rebuild in parallel without blocking each other.
    lock_key = _ADVISORY_LOCK_KEY ^ (hash(tenant_id) & 0x7FFFFFFF)
    locked = (await db.execute(
        text("SELECT pg_try_advisory_lock(:k)"), {"k": lock_key}
    )).scalar()
    if not locked:
        return {"status": "in_progress"}

    try:
        sig = await compute_ingest_signature(db)

        await db.execute(
            text("DELETE FROM listings_int_ext WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        await db.execute(
            text("DELETE FROM listings_int_hist WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        await db.execute(
            text("DELETE FROM keywords WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )

        params = {"tenant_id": tenant_id}
        await db.execute(_INSERT_HIST_SQL, params)
        await db.execute(_INSERT_EXT_SQL, params)
        await db.execute(_INSERT_KEYWORDS_SQL, params)

        n_ext = (await db.execute(
            text("SELECT count(*) FROM listings_int_ext WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )).scalar()
        n_hist = (await db.execute(
            text("SELECT count(*) FROM listings_int_hist WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )).scalar()
        n_kw = (await db.execute(
            text("SELECT count(*) FROM keywords WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )).scalar()

        duration_ms = int((time.monotonic() - t0) * 1000)
        row_counts = {"ext": n_ext, "hist": n_hist, "keywords": n_kw}

        await db.execute(
            text("""
                INSERT INTO refresh_state (id, last_refresh_at, ingest_signature, duration_ms, row_counts)
                VALUES (1, now(), :sig, :ms, CAST(:rc AS JSONB))
                ON CONFLICT (id) DO UPDATE SET
                    last_refresh_at  = EXCLUDED.last_refresh_at,
                    ingest_signature = EXCLUDED.ingest_signature,
                    duration_ms      = EXCLUDED.duration_ms,
                    row_counts       = EXCLUDED.row_counts
            """),
            {"sig": sig, "ms": duration_ms,
             "rc": __import__("json").dumps(row_counts)},
        )
        await db.commit()

        return {
            "status": "rebuilt",
            "ingest_signature": sig,
            "duration_ms": duration_ms,
            "row_counts": row_counts,
        }
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})
        await db.commit()


async def refresh_if_stale(db: AsyncSession, tenant_id: str, *, force: bool = False) -> dict:
    """Public entrypoint for /refresh + auto-trigger after import.

    Returns:
        {status: rebuilt|cached|in_progress, ...}
    """
    new_sig = await compute_ingest_signature(db)
    state = await get_state(db)

    if not force and state and state.get("ingest_signature") == new_sig:
        return {
            "status": "cached",
            "last_refresh_at": state.get("last_refresh_at"),
            "ingest_signature": new_sig,
            "row_counts": state.get("row_counts"),
        }

    return await rebuild_reporting(db, tenant_id)
