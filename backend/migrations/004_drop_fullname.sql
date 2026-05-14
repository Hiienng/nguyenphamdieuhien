-- Migration 004: Remove full_name column from users table
-- User identity is managed by id + email only

ALTER TABLE users DROP COLUMN IF EXISTS full_name;
