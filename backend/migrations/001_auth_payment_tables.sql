-- Migration 001: Auth + Payment tables
-- Run once against DATABASE_URL (Neon PostgreSQL)
-- Safe to re-run: uses CREATE TABLE IF NOT EXISTS

CREATE TABLE IF NOT EXISTS users (
    id          VARCHAR(36) PRIMARY KEY,
    email       VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name   VARCHAR(128),
    is_active   BOOLEAN NOT NULL DEFAULT true,
    is_admin    BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS subscriptions (
    id              VARCHAR(36) PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL REFERENCES users(id),
    plan            VARCHAR(32) NOT NULL DEFAULT 'monthly',
    status          VARCHAR(16) NOT NULL DEFAULT 'active',
    period_start    TIMESTAMPTZ,
    period_end      TIMESTAMPTZ,
    stripe_sub_id   VARCHAR(128),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);

CREATE TABLE IF NOT EXISTS credit_accounts (
    id          VARCHAR(36) PRIMARY KEY,
    user_id     VARCHAR(36) NOT NULL UNIQUE REFERENCES users(id),
    balance     INTEGER NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_accounts_user_id ON credit_accounts(user_id);

CREATE TABLE IF NOT EXISTS credit_transactions (
    id          VARCHAR(36) PRIMARY KEY,
    user_id     VARCHAR(36) NOT NULL REFERENCES users(id),
    amount      INTEGER NOT NULL,
    tx_type     VARCHAR(16) NOT NULL,
    description TEXT,
    stripe_pi_id VARCHAR(128),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_id ON credit_transactions(user_id);

CREATE TABLE IF NOT EXISTS payment_records (
    id              VARCHAR(36) PRIMARY KEY,
    user_id         VARCHAR(36) REFERENCES users(id),
    stripe_event_id VARCHAR(128) UNIQUE NOT NULL,
    event_type      VARCHAR(64) NOT NULL,
    amount_cents    INTEGER,
    currency        VARCHAR(8),
    payload         JSONB,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payment_records_user_id ON payment_records(user_id);
