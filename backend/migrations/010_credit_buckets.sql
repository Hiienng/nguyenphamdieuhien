-- Migration 010: Split credit_accounts.balance into two buckets
-- - subscription_credits: refilled with subscription plan, expires at end of cycle
-- - topup_credits:        purchased one-time, never expire
-- Keep `balance` column for backward compat; it stays in sync with sub + topup.
-- Also adds `bucket` column on credit_transactions to track which pool was touched.
-- Safe to re-run.

BEGIN;

-- 1. Add new columns to credit_accounts
ALTER TABLE credit_accounts
    ADD COLUMN IF NOT EXISTS subscription_credits INTEGER NOT NULL DEFAULT 0;

ALTER TABLE credit_accounts
    ADD COLUMN IF NOT EXISTS topup_credits INTEGER NOT NULL DEFAULT 0;

ALTER TABLE credit_accounts
    ADD COLUMN IF NOT EXISTS subscription_credits_reset_at TIMESTAMPTZ NULL;

-- 2. Backfill: treat existing balance as topup credits (never expire).
--    Only do this for rows where backfill hasn't happened yet
--    (subscription_credits = 0 AND topup_credits = 0 AND balance > 0).
UPDATE credit_accounts
SET topup_credits = balance
WHERE balance > 0
  AND subscription_credits = 0
  AND topup_credits = 0;

-- 3. Add bucket column to credit_transactions: "subscription" | "topup" | NULL (legacy)
ALTER TABLE credit_transactions
    ADD COLUMN IF NOT EXISTS bucket VARCHAR(16) NULL;

COMMIT;
