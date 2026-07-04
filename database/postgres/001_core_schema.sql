CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS players (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username TEXT NOT NULL UNIQUE,
  ideology TEXT NOT NULL CHECK (ideology IN ('Industrialist', 'Green', 'Socialist', 'Nationalist', 'Technocrat')),
  political_mmr INTEGER NOT NULL DEFAULT 1000,
  trust_score INTEGER NOT NULL DEFAULT 50 CHECK (trust_score BETWEEN 0 AND 100),
  private_account_balance BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cities (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  incumbent_player_id UUID REFERENCES players(id),
  opposition_player_id UUID REFERENCES players(id),
  gdp BIGINT NOT NULL DEFAULT 0,
  health_score INTEGER NOT NULL DEFAULT 50 CHECK (health_score BETWEEN 0 AND 100),
  unemployment INTEGER NOT NULL DEFAULT 20 CHECK (unemployment BETWEEN 0 AND 100),
  treasury BIGINT NOT NULL DEFAULT 0,
  cycle_day INTEGER NOT NULL DEFAULT 1 CHECK (cycle_day BETWEEN 1 AND 7)
);

CREATE TABLE IF NOT EXISTS election_cycles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  city_id TEXT NOT NULL REFERENCES cities(id),
  cycle_number INTEGER NOT NULL,
  incumbent_player_id UUID NOT NULL REFERENCES players(id),
  opposition_player_id UUID NOT NULL REFERENCES players(id),
  winner_player_id UUID REFERENCES players(id),
  practicality_score INTEGER CHECK (practicality_score BETWEEN 0 AND 100),
  rhetoric_score INTEGER CHECK (rhetoric_score BETWEEN 0 AND 100),
  city_performance_score INTEGER CHECK (city_performance_score BETWEEN 0 AND 100),
  final_trust_score INTEGER CHECK (final_trust_score BETWEEN 0 AND 100),
  starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ends_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS manifestos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  election_cycle_id UUID NOT NULL REFERENCES election_cycles(id) ON DELETE CASCADE,
  player_id UUID NOT NULL REFERENCES players(id),
  crises JSONB NOT NULL DEFAULT '[]'::jsonb,
  body TEXT NOT NULL,
  practicality_score INTEGER CHECK (practicality_score BETWEEN 0 AND 100),
  ai_notes JSONB NOT NULL DEFAULT '[]'::jsonb,
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS campaign_speeches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  election_cycle_id UUID NOT NULL REFERENCES election_cycles(id) ON DELETE CASCADE,
  player_id UUID NOT NULL REFERENCES players(id),
  audio_url TEXT,
  transcript TEXT NOT NULL,
  vision_share NUMERIC(4, 2),
  attack_share NUMERIC(4, 2),
  cta_share NUMERIC(4, 2),
  rhetoric_score INTEGER CHECK (rhetoric_score BETWEEN 0 AND 100),
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS budget_allocations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  city_id TEXT NOT NULL REFERENCES cities(id),
  player_id UUID NOT NULL REFERENCES players(id),
  fiscal_week INTEGER NOT NULL,
  department_name TEXT NOT NULL,
  portfolio_type TEXT NOT NULL CHECK (portfolio_type IN ('Industrial', 'Social', 'Strategic')),
  project_id TEXT NOT NULL,
  project_name TEXT NOT NULL,
  public_budget BIGINT NOT NULL CHECK (public_budget >= 0),
  actual_value BIGINT NOT NULL CHECK (actual_value >= 0),
  siphon_percent NUMERIC(5, 2) NOT NULL DEFAULT 0,
  graph_project_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS countries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  prime_minister_player_id UUID REFERENCES players(id),
  national_treasury BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS country_cities (
  country_id UUID NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
  city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
  mayor_player_id UUID NOT NULL REFERENCES players(id),
  joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (country_id, city_id)
);

CREATE TABLE IF NOT EXISTS federal_grants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  country_id UUID NOT NULL REFERENCES countries(id),
  city_id TEXT NOT NULL REFERENCES cities(id),
  prime_minister_player_id UUID NOT NULL REFERENCES players(id),
  amount BIGINT NOT NULL CHECK (amount >= 0),
  rationale TEXT NOT NULL,
  issued_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS no_confidence_votes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  country_id UUID NOT NULL REFERENCES countries(id),
  voter_player_id UUID NOT NULL REFERENCES players(id),
  prime_minister_player_id UUID NOT NULL REFERENCES players(id),
  vote BOOLEAN NOT NULL,
  voted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (country_id, voter_player_id, prime_minister_player_id)
);

CREATE TABLE IF NOT EXISTS trade_wars (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  aggressor_country_id UUID NOT NULL REFERENCES countries(id),
  defender_country_id UUID NOT NULL REFERENCES countries(id),
  starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ends_at TIMESTAMPTZ,
  aggressor_tariff INTEGER NOT NULL DEFAULT 0 CHECK (aggressor_tariff BETWEEN 0 AND 100),
  defender_tariff INTEGER NOT NULL DEFAULT 0 CHECK (defender_tariff BETWEEN 0 AND 100),
  winner_country_id UUID REFERENCES countries(id),
  gdp_buff_percent INTEGER NOT NULL DEFAULT 20
);

CREATE INDEX IF NOT EXISTS idx_budget_allocations_city_week ON budget_allocations(city_id, fiscal_week);
CREATE INDEX IF NOT EXISTS idx_manifestos_cycle_player ON manifestos(election_cycle_id, player_id);
CREATE INDEX IF NOT EXISTS idx_speeches_cycle_player ON campaign_speeches(election_cycle_id, player_id);

