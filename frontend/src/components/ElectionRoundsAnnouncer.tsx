"use client";

import { useEffect, useState } from "react";
import { Radio, Trophy } from "lucide-react";

const TOTAL_ROUNDS = 24;
const BATCH_SIZE = 4;
const TOTAL_BATCHES = TOTAL_ROUNDS / BATCH_SIZE; // 6
// 40 real-time minutes total, split evenly across the 6 batches
// (~6m40s each). Mirrored exactly in backend/app/services/coalition_engine.py
// (ELECTION_DURATION_SECONDS) and backend/app/services/incumbency_engine.py
// (COUNTING_DURATION_SECONDS) — keep all three in sync if this ever changes.
const TOTAL_DURATION_SECONDS = 40 * 60;
const BATCH_INTERVAL_SECONDS = TOTAL_DURATION_SECONDS / TOTAL_BATCHES;

export type AnnouncerRound = {
  round: number;
  running_incumbent_total: number;
  running_opposition_total: number;
};

export type AnnouncerParty = { name: string; color: string; finalSeats: number };

/**
 * Paces the reveal of a precomputed round-by-round result over real time,
 * instead of dumping the final tally the instant the simulation resolves —
 * "look like election result announcement": 4 rounds every ~6m40s, 40
 * minutes total. startedAt is a unix-seconds timestamp shared with the
 * server so every viewer's clock — and countdown to the final result —
 * agrees, regardless of when their own tab loaded.
 */
export default function ElectionRoundsAnnouncer({
  startedAt,
  rounds,
  parties,
  winnerName,
}: {
  startedAt: number; // unix seconds
  rounds: AnnouncerRound[];
  parties: AnnouncerParty[];
  winnerName: string;
}) {
  const [now, setNow] = useState(() => Date.now() / 1000);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(id);
  }, []);

  const elapsed = Math.max(0, now - startedAt);
  const batchesRevealed = Math.min(TOTAL_BATCHES, Math.floor(elapsed / BATCH_INTERVAL_SECONDS) + 1);
  const roundsRevealed = Math.min(TOTAL_ROUNDS, batchesRevealed * BATCH_SIZE);
  const complete = elapsed >= TOTAL_DURATION_SECONDS;
  const secondsToNextBatch = Math.max(0, BATCH_INTERVAL_SECONDS - (elapsed % BATCH_INTERVAL_SECONDS));
  const secondsToFinalResult = Math.max(0, TOTAL_DURATION_SECONDS - elapsed);
  const finalResultAt = new Date((startedAt + TOTAL_DURATION_SECONDS) * 1000);
  const currentRound = rounds[Math.min(roundsRevealed, rounds.length) - 1] ?? rounds[0];
  const totalFinalSeats = parties.reduce((s, p) => s + p.finalSeats, 0) || 1;

  function fmtClock(seconds: number) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  }

  function fmtWallClock(date: Date) {
    return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  }

  return (
    <div className="mt-3" style={{ border: "1px solid var(--pt-line)", background: "var(--pt-ink)" }}>
      <div className="flex items-center gap-2 border-b px-3 py-2" style={{ borderColor: "var(--pt-line)" }}>
        <Radio className="h-4 w-4" style={{ color: complete ? "var(--pt-green-lt)" : "var(--pt-red-lt)" }} />
        <span className="text-xs font-black uppercase" style={{ color: "var(--pt-white)" }}>
          {complete ? "Final Result Declared" : "🔴 Live Counting — Election Night"}
        </span>
        <span className="ml-auto text-[10px]" style={{ color: "var(--pt-muted)" }}>
          Round {Math.min(roundsRevealed, TOTAL_ROUNDS)}/{TOTAL_ROUNDS} · Batch {batchesRevealed}/{TOTAL_BATCHES}
        </span>
      </div>

      <div className="p-3">
        {!complete && (
          <div className="mb-3 text-center" style={{ borderBottom: "1px dashed var(--pt-line)", paddingBottom: "10px" }}>
            <div className="text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>
              Result Announced In
            </div>
            <div className="text-3xl font-black tabular-nums" style={{ color: "var(--pt-gold)" }}>
              {fmtClock(secondsToFinalResult)}
            </div>
            <div className="text-[10px]" style={{ color: "var(--pt-muted)" }}>
              Full result declared ~{fmtWallClock(finalResultAt)} · next 4 rounds in {fmtClock(secondsToNextBatch)}
            </div>
          </div>
        )}

        {/* Overall round progress */}
        <div className="mb-3 h-2 w-full" style={{ background: "var(--pt-panel-hi)" }}>
          <div
            className="h-2 transition-all duration-700"
            style={{ width: `${(roundsRevealed / TOTAL_ROUNDS) * 100}%`, background: "var(--pt-saffron)" }}
          />
        </div>

        {/* Per-party progressive reveal bars — each party's bar fills toward its
            final seat share only as fast as the overall round counter allows,
            so nobody sees the outcome before "counting" reaches that far. */}
        <div className="grid gap-2">
          {parties.map((party) => {
            const revealedSeats = Math.round(party.finalSeats * (roundsRevealed / TOTAL_ROUNDS));
            const widthPct = (party.finalSeats / totalFinalSeats) * 100;
            const fillPct = roundsRevealed / TOTAL_ROUNDS;
            return (
              <div key={party.name} className="flex items-center gap-2">
                <span className="w-24 flex-shrink-0 truncate text-[10px]" style={{ color: "var(--pt-muted)" }}>
                  {party.name}
                </span>
                <div className="h-4 flex-1" style={{ background: "var(--pt-panel-hi)" }}>
                  <div
                    className="h-4 transition-all duration-700"
                    style={{ width: `${widthPct * fillPct}%`, background: party.color }}
                  />
                </div>
                <span className="w-10 flex-shrink-0 text-right text-[10px] font-black" style={{ color: party.color }}>
                  {revealedSeats}
                </span>
              </div>
            );
          })}
        </div>

        {currentRound && (
          <div className="mt-3 flex items-center justify-between text-[10px]" style={{ color: "var(--pt-muted)" }}>
            <span>Round {currentRound.round} running tally</span>
            <span>
              {currentRound.running_incumbent_total.toLocaleString("en-IN")} vs{" "}
              {currentRound.running_opposition_total.toLocaleString("en-IN")}
            </span>
          </div>
        )}

        {complete && (
          <div
            className="mt-3 flex items-center justify-center gap-2 px-3 py-2 text-sm font-black"
            style={{ background: "var(--pt-saffron)", color: "#fff" }}
          >
            <Trophy className="h-4 w-4" />
            {winnerName} wins the 2029 Election!
          </div>
        )}
      </div>
    </div>
  );
}
