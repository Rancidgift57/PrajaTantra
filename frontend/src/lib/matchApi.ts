import { PlayerRole, SovereignState } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

export type SeatInfo = {
  player_id: string;
  username: string;
  role: PlayerRole;
};

export type MatchInfo = {
  match_id: string;
  join_code: string;
  status: "waiting" | "active" | "finished";
  incumbent: SeatInfo | null;
  opposition: SeatInfo | null;
  your_role: PlayerRole | null;
};

export type MatchStateResponse = {
  match: MatchInfo;
  state: SovereignState;
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

export const matchApi = {
  create: (token: string) => postJson<MatchInfo>("/api/match/create", { token }),
  join: (token: string, join_code: string) =>
    postJson<MatchInfo>("/api/match/join", { token, join_code }),
  getState: (matchId: string, token: string) =>
    getJson<MatchStateResponse>(`/api/match/${matchId}?token=${encodeURIComponent(token)}`),

  // Generic seat-scoped action call — server derives role from the token,
  // ignoring anything the client puts under `role` in payload.
  action: <TResponse>(matchId: string, path: string, token: string, payload: Record<string, unknown>) =>
    postJson<TResponse>(`/api/match/${matchId}/${path}`, { token, payload }),

  wsUrl: (matchId: string, token: string) =>
    `${WS_BASE}/api/match/ws/${matchId}?token=${encodeURIComponent(token)}`,
};
