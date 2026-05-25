-- Migration 009: Add full_name column to users table
-- Required by User ORM model (was added but never migrated)
-- Safe to re-run: uses ADD COLUMN IF NOT EXISTS

ALTER TABLE users
ADD COLUMN IF NOT EXISTS full_name VARCHAR(128);
