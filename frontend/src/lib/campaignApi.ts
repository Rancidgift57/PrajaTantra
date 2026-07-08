const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type CampaignCityInfo = {
  city_id: string;
  name: string;
  phase: number;
  voting_open: boolean;
  incumbent_player_id: string;
  opposition_player_id: string;
  incumbent_username: string;
  opposition_username: string;
  election_completed: boolean;
  winner_player_id: string | null;
  momentum_trust_buff: number;
  warnings: string[];
};

export type OffshoreAccountInfo = {
  player_id: string;
  username: string;
  balance: number;
  laundering_fee_pct: number;
  traced: boolean;
  frozen_until: number | null;
  ip_debuff_multiplier: number;
  ip_debuff_until: number | null;
};

export type CampaignState = {
  campaign_id: string;
  join_code: string;
  status: "waiting" | "active" | "finished";
  current_phase: number;
  total_phases: number;
  phase_schedule: string[][];
  cities: CampaignCityInfo[];
  accounts: OffshoreAccountInfo[];
  headlines: string[];
};

async function postJson<TResponse>(path: string, payload: unknown, params?: Record<string, string>): Promise<TResponse> {
  const qs = params ? `?${new URLSearchParams(params).toString()}` : "";
  const response = await fetch(`${API_BASE}${path}${qs}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Request failed: ${response.status}`);
  }
  return response.json() as Promise<TResponse>;
}

async function getJson<TResponse>(path: string): Promise<TResponse> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Request failed: ${response.status}`);
  }
  return response.json() as Promise<TResponse>;
}

export const campaignApi = {
  create: (hostPlayerId: string, hostUsername: string, cityNames: string[]) =>
    postJson<CampaignState>(
      "/api/campaign/create",
      { host_username: hostUsername, city_names: cityNames },
      { host_player_id: hostPlayerId },
    ),

  join: (playerId: string, joinCode: string, username: string) =>
    postJson<CampaignState>("/api/campaign/join", { join_code: joinCode, username }, { player_id: playerId }),

  state: (campaignId: string) => getJson<CampaignState>(`/api/campaign/${campaignId}/state`),

  siphonConstruct: (
    campaignId: string,
    playerId: string,
    cityId: string,
    construction: {
      role: "Incumbent";
      player_username: string;
      block_type: "Industrial" | "Social" | "Strategic";
      name: string;
      budget: number;
      siphon_percent: number;
      layer_depth?: number;
    },
  ) =>
    postJson<{
      city_state: unknown;
      offshore_balance: number;
      siphoned_gross: number;
      laundering_fee: number;
      siphoned_net: number;
      message: string;
    }>(`/api/campaign/${campaignId}/siphon-construct`, {
      player_id: playerId,
      city_id: cityId,
      construction,
    }),

  fundOpposition: (campaignId: string, playerId: string, targetCityId: string, amount: number) =>
    postJson<{ offshore_balance_remaining: number; influence_points_granted: number; message: string }>(
      `/api/campaign/${campaignId}/fund-opposition`,
      { player_id: playerId, target_city_id: targetCityId, amount },
    ),

  exposeLaundering: (campaignId: string, exposerPlayerId: string, sourceCityId: string, auditLevel = 3) =>
    postJson<{
      exposed_player_id: string;
      trust_penalty_applied: number;
      account_frozen: boolean;
      dried_up_cities: string[];
      message: string;
    }>(`/api/campaign/${campaignId}/expose-laundering`, {
      exposer_player_id: exposerPlayerId,
      source_city_id: sourceCityId,
      audit_level: auditLevel,
    }),

  runCityElection: (campaignId: string, playerId: string, cityId: string) =>
    postJson<{ winner_player_id: string; winner_username: string; momentum_applied_to: string[]; message: string }>(
      `/api/campaign/${campaignId}/elections/run`,
      { player_id: playerId, city_id: cityId },
    ),

  advancePhase: (campaignId: string, requestingPlayerId: string) =>
    postJson<{ newly_opened_cities: string[]; message: string }>(`/api/campaign/${campaignId}/phase/advance`, {
      requesting_player_id: requestingPlayerId,
    }),

  retaliate: (campaignId: string, actorPlayerId: string, sourceCityId: string) =>
    postJson<{ target_player_id: string; debuff_multiplier: number; debuff_seconds: number; message: string }>(
      `/api/campaign/${campaignId}/retaliate`,
      { actor_player_id: actorPlayerId, source_city_id: sourceCityId },
    ),
};
