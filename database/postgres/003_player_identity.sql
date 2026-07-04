-- 003_player_identity.sql
-- Adds the columns the real (Postgres-backed) AuthEngine needs directly on
-- `players`, so login/register/me/rename_city/leaderboard can all be single-
-- table queries.
--
-- Why not use the `cities` table from 001_core_schema.sql? That table
-- models a *city* as owned jointly by an incumbent_player_id and an
-- opposition_player_id — i.e. one row per match. That concept now lives in
-- the backend's in-memory MatchRegistry (backend/app/services/
-- match_registry.py) instead, keyed by match_id, not by a Postgres row.
-- `players.city_name` here is just the player's chosen display name shown
-- before they've even joined a match — safe to keep separate.
--
-- Safe to run multiple times (IF NOT EXISTS / IF NOT EXISTS guards).

ALTER TABLE players
  ADD COLUMN IF NOT EXISTS city_id TEXT,
  ADD COLUMN IF NOT EXISTS city_name TEXT NOT NULL DEFAULT 'Naya Shehar';

-- Backfill any pre-existing rows that don't have a city_id yet with a
-- deterministic placeholder derived from their own id, so the column can
-- later be made NOT NULL / UNIQUE if desired.
UPDATE players
SET city_id = 'CITY-' || upper(substr(id::text, 1, 6))
WHERE city_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_players_city_id ON players(city_id);
