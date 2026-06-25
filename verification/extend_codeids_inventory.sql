-- Extend codeids with fast-inventory metadata.
--
-- This migration preserves the repository's semantic model:
-- one row per codeid, with optional operational metadata captured from the
-- lightweight Influx inventory sync.

BEGIN;

ALTER TABLE codeids
    ADD COLUMN IF NOT EXISTS type TEXT,
    ADD COLUMN IF NOT EXISTS bucket TEXT,
    ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;

COMMIT;
