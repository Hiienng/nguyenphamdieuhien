-- Migration 006: Add tenant_id to reporting tables for multi-tenant isolation
--
-- listings_int_ext, listings_int_hist, keywords are materialized/rebuild-able
-- tables — safest approach is DROP + recreate via ensure_reporting_tables().
-- After running this migration, restart the backend. Each tenant's data will
-- be repopulated on their next "Tải lại" or on the next import confirm.

-- Drop in reverse dependency order (keywords → hist → ext)
DROP TABLE IF EXISTS keywords;
DROP TABLE IF EXISTS listings_int_hist;
DROP TABLE IF EXISTS listings_int_ext;

-- Recreate with tenant_id as first PK component
CREATE TABLE listings_int_ext (
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
);

CREATE TABLE listings_int_hist (
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
);

CREATE TABLE keywords (
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
);

CREATE INDEX IF NOT EXISTS idx_listings_int_ext_tenant  ON listings_int_ext  (tenant_id);
CREATE INDEX IF NOT EXISTS idx_listings_int_hist_tenant ON listings_int_hist (tenant_id);
CREATE INDEX IF NOT EXISTS idx_keywords_tenant          ON keywords           (tenant_id);
