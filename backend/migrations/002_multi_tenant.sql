-- Migration 002: Add tenant_id to all data tables
-- Run AFTER migration 001 (users table must exist)
-- Requires a seed admin user to exist first — see scripts/seed_admin_tenant.py

-- Step 1: Add nullable tenant_id columns
ALTER TABLE listings                ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36) REFERENCES users(id);
ALTER TABLE listing_report          ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36) REFERENCES users(id);
ALTER TABLE keyword_report          ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36) REFERENCES users(id);
ALTER TABLE manual_listing_report   ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36) REFERENCES users(id);
ALTER TABLE manual_keyword_report   ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36) REFERENCES users(id);
ALTER TABLE import_batch            ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36) REFERENCES users(id);
ALTER TABLE threshold_configs       ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36) REFERENCES users(id);
ALTER TABLE scenarios_rules         ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36) REFERENCES users(id);
ALTER TABLE listings_int_ext        ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36);
ALTER TABLE listings_int_hist       ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36);
ALTER TABLE keywords                ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36);

-- Step 2: Backfill existing rows with seed admin tenant
-- Replace :seed_tenant_id with actual UUID of admin user before running
-- UPDATE listings             SET tenant_id = :'seed_tenant_id' WHERE tenant_id IS NULL;
-- UPDATE listing_report       SET tenant_id = :'seed_tenant_id' WHERE tenant_id IS NULL;
-- UPDATE keyword_report       SET tenant_id = :'seed_tenant_id' WHERE tenant_id IS NULL;
-- UPDATE manual_listing_report SET tenant_id = :'seed_tenant_id' WHERE tenant_id IS NULL;
-- UPDATE manual_keyword_report SET tenant_id = :'seed_tenant_id' WHERE tenant_id IS NULL;
-- UPDATE import_batch         SET tenant_id = :'seed_tenant_id' WHERE tenant_id IS NULL;
-- UPDATE threshold_configs    SET tenant_id = :'seed_tenant_id' WHERE tenant_id IS NULL;
-- UPDATE scenarios_rules      SET tenant_id = :'seed_tenant_id' WHERE tenant_id IS NULL;
-- UPDATE listings_int_ext     SET tenant_id = :'seed_tenant_id' WHERE tenant_id IS NULL;
-- UPDATE listings_int_hist    SET tenant_id = :'seed_tenant_id' WHERE tenant_id IS NULL;
-- UPDATE keywords             SET tenant_id = :'seed_tenant_id' WHERE tenant_id IS NULL;

-- Step 3: Set NOT NULL (run after backfill is confirmed)
-- ALTER TABLE listings                ALTER COLUMN tenant_id SET NOT NULL;
-- ALTER TABLE listing_report          ALTER COLUMN tenant_id SET NOT NULL;
-- ALTER TABLE keyword_report          ALTER COLUMN tenant_id SET NOT NULL;
-- ALTER TABLE manual_listing_report   ALTER COLUMN tenant_id SET NOT NULL;
-- ALTER TABLE manual_keyword_report   ALTER COLUMN tenant_id SET NOT NULL;
-- ALTER TABLE import_batch            ALTER COLUMN tenant_id SET NOT NULL;
-- ALTER TABLE threshold_configs       ALTER COLUMN tenant_id SET NOT NULL;
-- ALTER TABLE scenarios_rules         ALTER COLUMN tenant_id SET NOT NULL;

-- Step 4: Indexes
CREATE INDEX IF NOT EXISTS idx_listings_tenant              ON listings(tenant_id);
CREATE INDEX IF NOT EXISTS idx_listing_report_tenant        ON listing_report(tenant_id);
CREATE INDEX IF NOT EXISTS idx_keyword_report_tenant        ON keyword_report(tenant_id);
CREATE INDEX IF NOT EXISTS idx_manual_listing_report_tenant ON manual_listing_report(tenant_id);
CREATE INDEX IF NOT EXISTS idx_manual_keyword_report_tenant ON manual_keyword_report(tenant_id);
CREATE INDEX IF NOT EXISTS idx_import_batch_tenant          ON import_batch(tenant_id);
CREATE INDEX IF NOT EXISTS idx_threshold_configs_tenant     ON threshold_configs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_rules_tenant       ON scenarios_rules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_listings_int_ext_tenant      ON listings_int_ext(tenant_id);
CREATE INDEX IF NOT EXISTS idx_listings_int_hist_tenant     ON listings_int_hist(tenant_id);
CREATE INDEX IF NOT EXISTS idx_keywords_tenant              ON keywords(tenant_id);

-- Step 5: refresh_state — add tenant_id (converts from singleton to per-tenant)
ALTER TABLE refresh_state ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36) REFERENCES users(id);
CREATE INDEX IF NOT EXISTS idx_refresh_state_tenant ON refresh_state(tenant_id);
