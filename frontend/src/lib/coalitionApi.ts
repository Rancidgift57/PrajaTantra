const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

export type Ideology = "Industrialist" | "Green" | "Socialist" | "Nationalist" | "Technocrat";
export type Ministry = "Infrastructure" | "Welfare" | "Finance";
export type CoalitionRole = "CM" | "Deputy CM" | "Minister" | "Leader of Opposition" | "Opposition" | "Fringe" | null;
export type CoalitionStatus = "waiting" | "negotiating" | "governing" | "floor_test" | "election" | "finished";

export type CoalitionSeat = {
  player_id: string;
  username: string;
  ideology: Ideology;
  party_seats: number;
  role: CoalitionRole;
  ministry: Ministry | null;
  war_chest: number;
  public_image_score: number;
  in_government: boolean;
  connected: boolean;
};

export type CoalitionProposal = {
  proposal_id: string;
  proposer_id: string;
  partner_ids: string[];
  accepted_by: string[];
  created_at: number;
};

export type FloorTestState = {
  active: boolean;
  triggered_by: string | null;
  deadline: number | null;
  votes: Record<string, "confidence" | "no_confidence">;
  last_resolved_at: number | null;
};

export type SeatResult = {
  party: string;
  role: "Incumbent" | "Opposition" | "Independent";
  seats: number;
  color: string;
  seat_share_pct: number;
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

export type ElectionResult = {
  rounds: CountingRoundResult[];
  final_incumbent_votes: number;
  final_opposition_votes: number;
  winner: string;
  margin: number;
  margin_pct: number;
  incumbent_name: string;
  opposition_name: string;
  total_rounds: number;
  total_seats: number;
  incumbent_seats: number;
  opposition_seats: number;
  seats: SeatResult[];
};

export type CoalitionMatchInfo = {
  match_id: string;
  join_code: string;
  status: CoalitionStatus;
  seats: CoalitionSeat[];
  government_player_ids: string[];
  opposition_player_ids: string[];
  government_seat_total: number;
  cm_player_id: string | null;
  lop_player_id: string | null;
  siphon_percentage: number;
  treasury: number;
  pending_proposals: CoalitionProposal[];
  floor_test: FloorTestState;
  negotiation_deadline: number | null;
  floor_test_cooldown_until: number;
  election_started_at: number | null;
  election_result: ElectionResult | null;
  election_seats_by_player: Record<string, number>;
  your_player_id: string | null;
  log: string[];
};

export type CoalitionStateResponse = { match: CoalitionMatchInfo };

export type CoalitionQuickMatchStatus = {
  status: "matched" | "waiting" | "idle";
  match: CoalitionMatchInfo | null;
  queue_size: number;
  needed: number;
};

async function postJson<TResponse>(path: string, payload: unknown): Promise<TResponse> {
  const response = await fetch(`${API_BASE}${path}`, {
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

export const coalitionApi = {
  create: (token: string) => postJson<CoalitionStateResponse>("/api/coalition/create", { token }),
  join: (token: string, join_code: string) =>
    postJson<CoalitionStateResponse>("/api/coalition/join", { token, join_code }),
  getState: (matchId: string, token: string) =>
    getJson<CoalitionStateResponse>(`/api/coalition/${matchId}?token=${encodeURIComponent(token)}`),

  quickmatchJoin: (token: string) =>
    postJson<CoalitionQuickMatchStatus>("/api/coalition/quickmatch/join", { token }),
  quickmatchStatus: (token: string) =>
    getJson<CoalitionQuickMatchStatus>(`/api/coalition/quickmatch/status?token=${encodeURIComponent(token)}`),
  quickmatchLeave: (token: string) =>
    postJson<{ left: boolean }>("/api/coalition/quickmatch/leave", { token }),

  propose: (matchId: string, token: string, partner_ids: string[]) =>
    postJson<CoalitionStateResponse>(`/api/coalition/${matchId}/propose`, { token, partner_ids }),
  respond: (matchId: string, token: string, proposal_id: string, accept: boolean) =>
    postJson<CoalitionStateResponse>(`/api/coalition/${matchId}/respond`, { token, proposal_id, accept }),
  allocateMinistry: (matchId: string, token: string, minister_id: string, ministry: Ministry) =>
    postJson<CoalitionStateResponse>(`/api/coalition/${matchId}/ministry`, { token, minister_id, ministry }),
  siphon: (matchId: string, token: string, amount: number, cuts: Record<string, number>) =>
    postJson<CoalitionStateResponse>(`/api/coalition/${matchId}/siphon`, { token, amount, cuts }),
  blackmail: (matchId: string, token: string, target_id: string, evidence_note: string, demand: "withdraw_support" | "leak_share") =>
    postJson<CoalitionStateResponse>(`/api/coalition/${matchId}/blackmail`, { token, target_id, evidence_note, demand }),
  withdrawSupport: (matchId: string, token: string) =>
    postJson<CoalitionStateResponse>(`/api/coalition/${matchId}/withdraw-support`, { token }),
  triggerFloorTest: (matchId: string, token: string) =>
    postJson<CoalitionStateResponse>(`/api/coalition/${matchId}/floor-test/trigger`, { token }),
  castFloorVote: (matchId: string, token: string, vote: "confidence" | "no_confidence") =>
    postJson<CoalitionStateResponse>(`/api/coalition/${matchId}/floor-test/vote`, { token, vote }),
  startElection: (matchId: string, token: string) =>
    postJson<CoalitionStateResponse>(`/api/coalition/${matchId}/election/start`, { token }),

  wsUrl: (matchId: string, token: string) =>
    `${WS_BASE}/api/coalition/ws/${matchId}?token=${encodeURIComponent(token)}`,
};
