-- 002_auth_columns.sql
-- Adds authentication + city-naming support to the existing `players` and
-- `cities` tables created in 001_core_schema.sql.
--
-- This is purely additive — no existing column is touched, so it's safe to
-- run on a database that already has the original schema applied.
--
-- The in-memory AuthEngine (backend/app/services/auth_engine.py) currently
-- ships as a self-contained demo store so the project runs with zero DB
-- setup. To move auth to real Postgres persistence:
--   1. Run this migration.
--   2. Replace the dict-based stores in AuthEngine with SQLAlchemy/asyncpg
--      calls using the same method signatures (register/login/me/
--      rename_city/leaderboard) — nothing in the router or frontend needs
--      to change.

ALTER TABLE players
  ADD COLUMN IF NOT EXISTS email TEXT UNIQUE,
  ADD COLUMN IF NOT EXISTS password_hash TEXT,
  ADD COLUMN IF NOT EXISTS owned_percent NUMERIC(5, 2) NOT NULL DEFAULT 0.1,
  ADD COLUMN IF NOT EXISTS gold BIGINT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS max_troops INTEGER NOT NULL DEFAULT 0;

-- cities.name already exists from 001_core_schema.sql and is used directly
-- for the player-chosen city name set at registration / rename time.

CREATE INDEX IF NOT EXISTS idx_players_email ON players(email);
CREATE INDEX IF NOT EXISTS idx_players_owned_percent ON players(owned_percent DESC);