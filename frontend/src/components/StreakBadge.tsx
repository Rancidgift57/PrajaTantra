"use client";

import { useEffect, useState } from "react";

const STREAK_KEY = "prajatantra.streak.v1";

type StreakData = {
  currentStreak: number;
  bestStreak: number;
  wins: number;
  losses: number;
  lastResult: "win" | "loss" | null;
};

const DEFAULT_STREAK: StreakData = { currentStreak: 0, bestStreak: 0, wins: 0, losses: 0, lastResult: null };

function loadStreak(): StreakData {
  try {
    const raw = localStorage.getItem(STREAK_KEY);
    return raw ? { ...DEFAULT_STREAK, ...JSON.parse(raw) } : DEFAULT_STREAK;
  } catch {
    return DEFAULT_STREAK;
  }
}

function saveStreak(data: StreakData) {
  try {
    localStorage.setItem(STREAK_KEY, JSON.stringify(data));
  } catch { /* ignore */ }
}

/** Call this after an election resolves to update the persisted streak. */
export function recordMatchResult(won: boolean): StreakData {
  const prev = loadStreak();
  const next: StreakData = won
    ? {
        currentStreak: prev.lastResult === "loss" || prev.currentStreak < 0 ? 1 : prev.currentStreak + 1,
        bestStreak: Math.max(prev.bestStreak, prev.lastResult === "loss" ? 1 : prev.currentStreak + 1),
        wins: prev.wins + 1,
        losses: prev.losses,
        lastResult: "win",
      }
    : {
        currentStreak: 0,
        bestStreak: prev.bestStreak,
        wins: prev.wins,
        losses: prev.losses + 1,
        lastResult: "loss",
      };
  saveStreak(next);
  return next;
}

export default function StreakBadge() {
  const [streak, setStreak] = useState<StreakData>(DEFAULT_STREAK);

  useEffect(() => {
    setStreak(loadStreak());
    // Keep in sync if another tab updates it, or recordMatchResult fires locally.
    function onStorage(e: StorageEvent) {
      if (e.key === STREAK_KEY) setStreak(loadStreak());
    }
    window.addEventListener("storage", onStorage);
    const poll = setInterval(() => setStreak(loadStreak()), 2000);
    return () => {
      window.removeEventListener("storage", onStorage);
      clearInterval(poll);
    };
  }, []);

  const isHot = streak.currentStreak >= 2;
  const totalGames = streak.wins + streak.losses;
  const winRate = totalGames > 0 ? Math.round((streak.wins / totalGames) * 100) : 0;

  return (
    <div
      className="flex items-center gap-3 px-3 py-1.5 text-[10px]"
      style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}
      title={`${streak.wins}W - ${streak.losses}L · Best streak ${streak.bestStreak} · Win rate ${winRate}%`}
    >
      <span className="flex items-center gap-1 font-black" style={{ color: isHot ? "var(--pt-gold)" : "var(--pt-muted)" }}>
        {isHot ? "🔥" : "🎯"} {streak.currentStreak > 0 ? `${streak.currentStreak} Streak` : "No Streak"}
      </span>
      <span style={{ color: "var(--pt-muted)" }}>|</span>
      <span style={{ color: "var(--pt-muted)" }}>
        Best <span style={{ color: "var(--pt-saffron)" }}>{streak.bestStreak}</span>
      </span>
      <span style={{ color: "var(--pt-muted)" }}>|</span>
      <span style={{ color: "var(--pt-muted)" }}>
        {winRate}% WR ({streak.wins}-{streak.losses})
      </span>
    </div>
  );
}
