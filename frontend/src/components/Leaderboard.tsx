"use client";

import { BarChart3, Plus, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api, LeaderboardResponse } from "@/lib/api";

/**
 * Leaderboard — recreates the OpenFront-style world ranking table from the
 * reference screenshot: a small floating panel, top-left, with columns
 * # / Player / Owned / Gold / Max troops, a session code in the corner,
 * and a "+" button to expand to more rows.
 */
export default function Leaderboard({ token }: { token: string | null }) {
  const [data, setData] = useState<LeaderboardResponse | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [sessionCode] = useState(() => Math.random().toString(36).slice(2, 10));

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await api.leaderboard(token ?? undefined, expanded ? 15 : 5);
        if (!cancelled) setData(result);
      } catch {
        // Silent fail — leaderboard is non-critical chrome
      }
    }
    load();
    const interval = setInterval(load, 8000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [token, expanded]);

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => setCollapsed(false)}
        className="fixed left-4 top-4 z-40 flex h-10 w-10 items-center justify-center"
        style={{ background: "var(--pt-panel)", border: "1px solid var(--pt-line)" }}
        aria-label="Leaderboard kholein"
      >
        <BarChart3 className="h-5 w-5" style={{ color: "var(--pt-saffron)" }} />
      </button>
    );
  }

  return (
    <div
      className="fixed left-4 top-4 z-40 w-[300px]"
      style={{ background: "var(--pt-panel)", border: "1px solid var(--pt-line)", boxShadow: "0 18px 60px rgba(0,0,0,0.4)" }}
    >
      {/* Header bar */}
      <div
        className="flex items-center justify-between px-3 py-2"
        style={{ borderBottom: "1px solid var(--pt-line)" }}
      >
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          className="flex h-7 w-7 items-center justify-center"
          style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)" }}
        >
          <BarChart3 className="h-4 w-4" style={{ color: "var(--pt-saffron)" }} />
        </button>
        <span className="font-mono text-[10px]" style={{ color: "var(--pt-muted)" }}>
          {sessionCode}
        </span>
      </div>

      {/* Table */}
      <table className="w-full text-sm">
        <thead>
          <tr style={{ color: "var(--pt-muted)" }} className="text-xs">
            <th className="px-3 py-2 text-left font-semibold">#</th>
            <th className="px-1 py-2 text-left font-semibold">Player</th>
            <th className="px-1 py-2 text-right font-semibold">Owned ↓</th>
            <th className="px-1 py-2 text-right font-semibold">Gold</th>
            <th className="px-3 py-2 text-right font-semibold">Max troops</th>
          </tr>
        </thead>
        <tbody>
          {(data?.entries ?? []).map((entry) => (
            <tr
              key={entry.player_id}
              style={
                entry.is_you
                  ? { background: "rgba(255,107,0,0.12)", fontWeight: 800 }
                  : undefined
              }
            >
              <td className="px-3 py-2" style={{ color: "var(--pt-muted)" }}>{entry.rank}</td>
              <td className="px-1 py-2">
                <div className="leading-tight">
                  <div style={{ color: entry.is_you ? "var(--pt-saffron)" : "var(--pt-white)" }}>
                    {entry.player_username}
                  </div>
                  <div className="text-[10px]" style={{ color: "var(--pt-muted)" }}>{entry.city_name}</div>
                </div>
              </td>
              <td className="px-1 py-2 text-right">{entry.owned_percent.toFixed(1)}%</td>
              <td className="px-1 py-2 text-right" style={{ color: "var(--pt-gold)" }}>
                {formatK(entry.gold)}
              </td>
              <td className="px-3 py-2 text-right" style={{ color: "var(--pt-wheel-lt)" }}>
                {formatK(entry.max_troops)}
              </td>
            </tr>
          ))}
          {(data?.entries?.length ?? 0) === 0 && (
            <tr>
              <td colSpan={5} className="px-3 py-4 text-center text-xs" style={{ color: "var(--pt-muted)" }}>
                Vishwa rank load ho raha hai…
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* Expand / collapse footer */}
      <div className="flex justify-center py-2" style={{ borderTop: "1px solid var(--pt-line)" }}>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex h-7 w-7 items-center justify-center"
          style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)" }}
          aria-label={expanded ? "Kam dikhayein" : "Aur dikhayein"}
        >
          {expanded ? <X className="h-4 w-4" style={{ color: "var(--pt-muted)" }} /> : <Plus className="h-4 w-4" style={{ color: "var(--pt-muted)" }} />}
        </button>
      </div>
    </div>
  );
}

function formatK(value: number) {
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return `${value}`;
}