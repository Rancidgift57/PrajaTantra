export type GraphNode = {
  id: string;
  label: string;
  name: string;
  properties: Record<string, string | number | boolean>;
};

export type GraphEdge = {
  source: string;
  target: string;
  type: string;
  properties: Record<string, string | number | boolean>;
};

export type ScamResponse = {
  project_id: string;
  cypher: string;
  parameters: Record<string, string | number | boolean>;
  nodes: GraphNode[];
  edges: GraphEdge[];
  graph_backend: "neo4j" | "memory";
};

export type AuditPath = {
  hop_count: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  suspicion_score: number;
};

export type AuditResponse = {
  project_id: string | null;
  project_name: string;
  audit_level: number;
  corruption_detected: boolean;
  smoking_gun: string | null;
  paths: AuditPath[];
  next_upgrade_hint: string;
};

export type ElectionResponse = {
  practicality_score: number;
  rhetoric_score: number;
  city_performance_score: number;
  trust_score: number;
  penalties: string[];
  breakdown: Record<string, string | number>;
};

export type PlayerRole = "Incumbent" | "Opposition";
export type PortfolioType = "Industrial" | "Social" | "Strategic";

export type CityStats = {
  gdp: number;
  health: number;
  treasury: number;
  unemployment: number;
  corruption_leaks: number;
  public_trust: number;
  pollution: number;
  worker_unrest: number;
  national_prestige: number;
};

export type InfrastructureBlock = {
  id: string;
  name: string;
  portfolio_type: PortfolioType;
  level: number;
  gold_per_tick: number;
  maintenance: number;
  pollution_delta: number;
  unrest_delta: number;
  trust_delta: number;
  prestige_delta: number;
};

export type SovereignState = {
  cycle_day: number;
  active_role: PlayerRole;
  incumbent: string;
  opposition: string;
  city: CityStats;
  blocks: InfrastructureBlock[];
  influence_points: number;
  audit_level: number;
  headlines: string[];
  federal_grants: string[];
  trade_buffs: string[];
  emergency_powers: boolean;
};

export type ConstructionResponse = {
  state: SovereignState;
  scam: ScamResponse;
  message: string;
};

export type StrikeResponse = {
  state: SovereignState;
  revenue_loss: number;
  unrest_added: number;
  message: string;
};

export type LeakResponse = {
  state: SovereignState;
  trust_damage: number;
  headline: string;
};

export type FederalGrantResponse = {
  state: SovereignState;
  national_treasury_remaining: number;
  message: string;
};

export type TradeDuelResponse = {
  winner: string;
  country_score: number;
  rival_score: number;
  gdp_buff_percent: number;
  state: SovereignState;
};

// ── Incumbency Wave types ──────────────────────────────────────────────────

export type IncumbencyWaveRequest = {
  global_trust: number;
  scams_exposed: number;
  consecutive_terms: number;
};

export type IncumbencyWaveResponse = {
  incumbency_factor: number;
  wave_label: string;
  is_pro_incumbency: boolean;
  trust_delta: number;
  scandal_drag: number;
  fatigue_drag: number;
};

export type CountingRoundResult = {
  round: number;
  incumbent_votes: number;
  opposition_votes: number;
  incumbent_share: number;
  opposition_share: number;
  running_incumbent_total: number;
  running_opposition_total: number;
};

export type TenRoundSimulationRequest = {
  global_trust: number;
  scams_exposed: number;
  consecutive_terms: number;
  incumbent_name: string;
  opposition_name: string;
  incumbent_match_score: number;
  opposition_match_score: number;
  total_electorate: number;
  total_seats?: number;
  manifesto_trust_score?: number | null;
};

export type SeatResult = {
  party: string;
  role: "Incumbent" | "Opposition" | "Independent";
  seats: number;
  color: string;
  seat_share_pct: number;
};

export type TenRoundSimulationResponse = {
  incumbency_factor: number;
  wave_label: string;
  rounds: CountingRoundResult[];
  final_incumbent_votes: number;
  final_opposition_votes: number;
  winner: string;
  margin: number;
  margin_pct: number;
  // Names echo'd back from the request
  incumbent_name?: string;
  opposition_name?: string;

  // Election-day scheduling
  election_cycle_days: number;
  counting_duration_hours: number;
  total_rounds: number;

  // Seat map (hemicycle chart)
  total_seats: number;
  incumbent_seats: number;
  opposition_seats: number;
  independent_seats: number;
  seats: SeatResult[];

  // Emergency / supermajority powers
  emergency_eligible: boolean;
  emergency_threshold_pct: number;
  emergency_message: string | null;
};

export type EmergencyRequest = {
  role: PlayerRole;
  incumbent_seats: number;
  total_seats: number;
  threshold_pct?: number;
};

export type EmergencyResponse = {
  state: SovereignState;
  granted: boolean;
  seat_share_pct: number;
  message: string;
};

// ── Auth / Profile / Leaderboard types ─────────────────────────────────────

export type Ideology = "Industrialist" | "Green" | "Socialist" | "Nationalist" | "Technocrat";

export type PlayerProfile = {
  id: string;
  username: string;
  email: string;
  city_id: string;
  city_name: string;
  ideology: Ideology;
  political_mmr: number;
  created_at: string;
};

export type RegisterPayload = {
  username: string;
  email: string;
  password: string;
  city_name: string;
  ideology: Ideology;
};

export type LoginPayload = {
  username_or_email: string;
  password: string;
};

export type AuthResponse = {
  token: string;
  player: PlayerProfile;
  message: string;
};

export type RenameCityResponse = {
  city_id: string;
  city_name: string;
  message: string;
};

export type LeaderboardEntry = {
  rank: number;
  player_id: string;
  player_username: string;
  city_name: string;
  owned_percent: number;
  gold: number;
  max_troops: number;
  is_you: boolean;
};

export type LeaderboardResponse = {
  entries: LeaderboardEntry[];
  total_players: number;
  your_rank: number | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function getJson<TResponse>(path: string): Promise<TResponse> {
  const response = await fetch(`${API_BASE}${path}`);

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<TResponse>;
}

async function postJson<TResponse, TPayload>(path: string, payload: TPayload): Promise<TResponse> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<TResponse>;
}

export const api = {
  getState: () => getJson<SovereignState>("/api/prajatantra/state"),
  buildInfrastructure: (payload: Record<string, string | number>) =>
    postJson<ConstructionResponse, Record<string, string | number>>("/api/prajatantra/construction/build", payload),
  organizeStrike: (payload: { role: PlayerRole; target_block_id: string; influence_spend: number }) =>
    postJson<StrikeResponse, { role: PlayerRole; target_block_id: string; influence_spend: number }>(
      "/api/prajatantra/opposition/strike",
      payload,
    ),
  leakAudit: (payload: { role: PlayerRole; audit: AuditResponse }) =>
    postJson<LeakResponse, { role: PlayerRole; audit: AuditResponse }>("/api/prajatantra/opposition/leak", payload),
  issueFederalGrant: (payload: Record<string, string | number>) =>
    postJson<FederalGrantResponse, Record<string, string | number>>("/api/prajatantra/federal/grant", payload),
  resolveTradeDuel: (payload: Record<string, string | number>) =>
    postJson<TradeDuelResponse, Record<string, string | number>>("/api/prajatantra/global/trade-duel", payload),
  createLayeredScam: (payload: Record<string, string | number>) =>
    postJson<ScamResponse, Record<string, string | number>>("/api/prajatantra/scams/layered", payload),
  auditProject: (payload: { project_id?: string; project_name: string; audit_level: number }) =>
    postJson<AuditResponse, { project_id?: string; project_name: string; audit_level: number }>(
      "/api/prajatantra/audits/project",
      payload,
    ),
  gradeElection: (payload: Record<string, unknown>) =>
    postJson<ElectionResponse, Record<string, unknown>>("/api/prajatantra/elections/grade", payload),
  headlines: (payload: Record<string, string | number>) =>
    postJson<{ headlines: string[] }, Record<string, string | number>>("/api/prajatantra/media/headlines", payload),
  computeIncumbencyWave: (payload: IncumbencyWaveRequest) =>
    postJson<IncumbencyWaveResponse, IncumbencyWaveRequest>(
      "/api/prajatantra/elections/incumbency-wave",
      payload,
    ),
  simulateTenRoundCounting: (payload: TenRoundSimulationRequest) =>
    postJson<TenRoundSimulationResponse, TenRoundSimulationRequest>(
      "/api/prajatantra/elections/simulate-counting",
      payload,
    ),
  declareEmergency: (payload: EmergencyRequest) =>
    postJson<EmergencyResponse, EmergencyRequest>("/api/prajatantra/emergency/declare", payload),

  // ── Auth / Profile / City naming / Leaderboard ────────────────────────────
  register: (payload: RegisterPayload) =>
    postJson<AuthResponse, RegisterPayload>("/api/auth/register", payload),
  login: (payload: LoginPayload) =>
    postJson<AuthResponse, LoginPayload>("/api/auth/login", payload),
  me: (token: string) => getJson<{ player: PlayerProfile }>(`/api/auth/me?token=${encodeURIComponent(token)}`),
  renameCity: (token: string, new_name: string) =>
    postJson<RenameCityResponse, { token: string; new_name: string }>("/api/auth/city/rename", { token, new_name }),
  leaderboard: (token?: string, limit = 5) =>
    getJson<LeaderboardResponse>(
      `/api/auth/leaderboard?limit=${limit}${token ? `&token=${encodeURIComponent(token)}` : ""}`,
    ),

  // ── City Development ──────────────────────────────────────────────────────
  buildingCatalog: () =>
    getJson<BuildingCatalogResponse>("/api/development/buildings/catalog"),
  buildFromCatalog: (payload: BuildFromCatalogPayload) =>
    postJson<CityDevelopmentResponse, BuildFromCatalogPayload>("/api/development/buildings/build", payload),
  schemeCatalog: () =>
    getJson<SchemeCatalogResponse>("/api/development/schemes/catalog"),
  launchScheme: (payload: LaunchSchemePayload) =>
    postJson<LaunchSchemeResponse, LaunchSchemePayload>("/api/development/schemes/launch", payload),
  activeSchemes: () =>
    getJson<ActiveScheme[]>("/api/development/schemes/active"),
};

// ── Development types ───────────────────────────────────────────────────────

export type BuildingId =
  | "PORT" | "MALL" | "FACTORY" | "WASTE_PLANT"
  | "TECH_PARK" | "POWER_GRID" | "SCHOOL_NETWORK" | "HOSPITAL_CHAIN";

export type SchemeId =
  | "SUBSIDY_MSME" | "FREE_HEALTHCARE" | "SWACHH_ABHIYAN"
  | "SKILL_MISSION" | "GREEN_ENERGY_SUBSIDY" | "FARMER_LOAN_WAIVER";

export type BuildingCatalogEntry = {
  id: BuildingId;
  name: string;
  hindi_name: string;
  portfolio_type: PortfolioType;
  description: string;
  base_cost: number;
  gold_per_tick: number;
  maintenance: number;
  pollution_delta: number;
  unrest_delta: number;
  trust_delta: number;
  prestige_delta: number;
  employment_delta: number;
  pros: string[];
  cons: string[];
};

export type BuildingCatalogResponse = {
  buildings: BuildingCatalogEntry[];
};

export type BuildFromCatalogPayload = {
  role: PlayerRole;
  player_username: string;
  building_id: BuildingId;
  custom_name?: string;
  budget: number;
  siphon_percent: number;
  layer_depth: number;
};

export type CityDevelopmentResponse = {
  state: SovereignState;
  block: InfrastructureBlock;
  message: string;
};

export type SchemeCatalogEntry = {
  id: SchemeId;
  name: string;
  hindi_name: string;
  description: string;
  upfront_cost: number;
  cost_per_tick: number;
  duration_cycles: number;
  trust_delta: number;
  unrest_delta: number;
  employment_delta: number;
  pollution_delta: number;
  gdp_multiplier_percent: number;
  pros: string[];
  cons: string[];
};

export type SchemeCatalogResponse = {
  schemes: SchemeCatalogEntry[];
};

export type LaunchSchemePayload = {
  role: PlayerRole;
  scheme_id: SchemeId;
};

export type ActiveScheme = {
  scheme_id: SchemeId;
  name: string;
  hindi_name: string;
  cycles_remaining: number;
  cost_per_tick: number;
};

export type LaunchSchemeResponse = {
  state: SovereignState;
  active_scheme: ActiveScheme;
  message: string;
};

// ── Narrow client shapes so per-match adapters (see lib/matchApiAdapter.ts)
// can be swapped into CityDevelopment / CityMap without changing their
// component code beyond accepting an `apiClient` prop. ──────────────────
export type DevApiClient = Pick<
  typeof api,
  "buildingCatalog" | "buildFromCatalog" | "schemeCatalog" | "launchScheme" | "activeSchemes"
>;