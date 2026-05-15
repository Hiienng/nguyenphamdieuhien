-- Migration 007: Row-Level Security (RLS) for tenant isolation
--
-- Creates app_user role for backend (non-superuser, limited to DML).
-- Enables RLS on all tenant-scoped tables so Postgres enforces isolation
-- even if application code forgets WHERE tenant_id.
--
-- Pattern: backend sets  SET LOCAL app.tenant_id = '<uuid>'  at the start
-- of every request session. RLS policies read this setting.
-- neondb_owner bypasses RLS (for migrations and admin scripts).

-- ── Role ────────────────────────────────────────────────────────────────────
-- NOTE: Change the password before running in production!
CREATE ROLE app_user WITH LOGIN PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
GRANT CONNECT ON DATABASE neondb TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_user;

-- ── Raw ingest tables ────────────────────────────────────────────────────────
ALTER TABLE listing_report        ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36);
ALTER TABLE keyword_report        ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36);
CREATE INDEX IF NOT EXISTS idx_listing_report_tenant        ON listing_report  (tenant_id);
CREATE INDEX IF NOT EXISTS idx_keyword_report_tenant        ON keyword_report  (tenant_id);

ALTER TABLE listing_report        ENABLE ROW LEVEL SECURITY;
ALTER TABLE listing_report        FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON listing_report
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY owner_bypass ON listing_report TO neondb_owner USING (true) WITH CHECK (true);

ALTER TABLE manual_listing_report ENABLE ROW LEVEL SECURITY;
ALTER TABLE manual_listing_report FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON manual_listing_report
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY owner_bypass ON manual_listing_report TO neondb_owner USING (true) WITH CHECK (true);

ALTER TABLE keyword_report        ENABLE ROW LEVEL SECURITY;
ALTER TABLE keyword_report        FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON keyword_report
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY owner_bypass ON keyword_report TO neondb_owner USING (true) WITH CHECK (true);

ALTER TABLE manual_keyword_report ENABLE ROW LEVEL SECURITY;
ALTER TABLE manual_keyword_report FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON manual_keyword_report
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY owner_bypass ON manual_keyword_report TO neondb_owner USING (true) WITH CHECK (true);

-- ── Threshold configs ────────────────────────────────────────────────────────
ALTER TABLE threshold_configs ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36);
CREATE INDEX IF NOT EXISTS idx_threshold_configs_tenant ON threshold_configs (tenant_id);

ALTER TABLE threshold_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE threshold_configs FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON threshold_configs
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY owner_bypass ON threshold_configs TO neondb_owner USING (true) WITH CHECK (true);

-- ── Reporting tables (rebuilt per tenant) ────────────────────────────────────
ALTER TABLE listings_int_ext  ENABLE ROW LEVEL SECURITY;
ALTER TABLE listings_int_ext  FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON listings_int_ext
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY owner_bypass ON listings_int_ext TO neondb_owner USING (true) WITH CHECK (true);

ALTER TABLE listings_int_hist ENABLE ROW LEVEL SECURITY;
ALTER TABLE listings_int_hist FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON listings_int_hist
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY owner_bypass ON listings_int_hist TO neondb_owner USING (true) WITH CHECK (true);

ALTER TABLE keywords ENABLE ROW LEVEL SECURITY;
ALTER TABLE keywords FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON keywords
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY owner_bypass ON keywords TO neondb_owner USING (true) WITH CHECK (true);
