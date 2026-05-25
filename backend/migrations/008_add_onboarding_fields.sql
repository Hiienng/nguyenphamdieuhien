-- Migration 008: Add onboarding fields to users table
-- Run once against DATABASE_URL (Neon PostgreSQL)
-- Safe to re-run: uses ALTER TABLE IF NOT EXISTS

-- Add onboarding columns
ALTER TABLE users
ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS product_categories JSONB NOT NULL DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS seller_location VARCHAR(8),
ADD COLUMN IF NOT EXISTS last_onboarding_update TIMESTAMPTZ;
