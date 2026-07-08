"use client";

import { useState } from "react";
import { MatchInfo, matchApi } from "@/lib/matchApi";

type Props = {
  token: string;
  onMatched: (match: MatchInfo) => void;
};

export default function MatchLobby({ token, onMatched }: Props) {
  const [mode, setMode] = useState<"idle" | "hosting" | "joining">("idle");
  const [joinCode, setJoinCode] = useState("");
  const [hostedMatch, setHostedMatch] = useState<MatchInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleCreate() {
    setBusy(true);
    setError(null);
    try {
      const match = await matchApi.create(token);
      setHostedMatch(match);
      setMode("hosting");
      onMatched(match); // host can already see the waiting room / their own city
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create match.");
    } finally {
      setBusy(false);
    }
  }

  async function handleJoin() {
    if (!joinCode.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const match = await matchApi.join(token, joinCode.trim().toUpperCase());
      onMatched(match);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not join match.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="mx-auto mt-16 max-w-md p-6"
      style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}
    >
      <div className="mb-1 font-black text-lg">Match Banayein ya Join Karein</div>
      <div className="mb-5 text-[11px]" style={{ color: "var(--pt-muted)" }}>
        Do khiladi, ek shehar. Ek Incumbent shehar banata hai, doosra Opposition uska audit karta hai.
      </div>

      {error && (
        <div
          className="mb-4 px-3 py-2 text-[11px]"
          style={{ border: "1px solid var(--pt-red)", color: "var(--pt-red-lt)" }}
        >
          {error}
        </div>
      )}

      {mode !== "hosting" && (
        <div className="mb-4 flex gap-2">
          <button
            type="button"
            onClick={handleCreate}
            disabled={busy}
            className="flex-1 px-3 py-2 text-xs font-bold uppercase"
            style={{ background: "var(--pt-saffron)", color: "#fff" }}
          >
            🏙️ Naya Match Banayein
          </button>
          <button
            type="button"
            onClick={() => setMode("joining")}
            disabled={busy}
            className="flex-1 px-3 py-2 text-xs font-bold uppercase"
            style={{ border: "1px solid var(--pt-line)", color: "var(--pt-muted)" }}
          >
            🔑 Code se Join Karein
          </button>
        </div>
      )}

      {mode === "hosting" && hostedMatch && (
        <div className="mb-4 p-4 text-center" style={{ border: "1px dashed var(--pt-saffron)" }}>
          <div className="text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>
            Apna opponent ko yeh code bhejein
          </div>
          <div className="my-2 text-3xl font-black tracking-widest" style={{ color: "var(--pt-saffron)" }}>
            {hostedMatch.join_code}
          </div>
          <div className="text-[10px]" style={{ color: "var(--pt-muted)" }}>
            Waiting for Opposition to join... aap Incumbent hain.
          </div>
        </div>
      )}

      {mode === "joining" && (
        <div className="flex gap-2">
          <input
            value={joinCode}
            onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
            placeholder="e.g. K4N7QX"
            maxLength={6}
            className="flex-1 px-3 py-2 text-sm tracking-widest"
            style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)", color: "#fff" }}
          />
          <button
            type="button"
            onClick={handleJoin}
            disabled={busy || joinCode.trim().length < 4}
            className="px-4 py-2 text-xs font-bold uppercase"
            style={{ background: "var(--pt-saffron)", color: "#fff" }}
          >
            Join
          </button>
        </div>
      )}
    </div>
  );
}
