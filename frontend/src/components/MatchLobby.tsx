"use client";

import { useEffect, useRef, useState } from "react";
import { MatchInfo, matchApi } from "@/lib/matchApi";

type Props = {
  token: string;
  onMatched: (match: MatchInfo) => void;
};

const QUICKMATCH_POLL_MS = 2000;

export default function MatchLobby({ token, onMatched }: Props) {
  const [mode, setMode] = useState<"idle" | "hosting" | "joining" | "quickmatching">("idle");
  const [joinCode, setJoinCode] = useState("");
  const [hostedMatch, setHostedMatch] = useState<MatchInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [queueSize, setQueueSize] = useState(0);
  const [queuedSeconds, setQueuedSeconds] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const secondsRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopQuickmatchTimers() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (secondsRef.current) { clearInterval(secondsRef.current); secondsRef.current = null; }
  }

  // Clean up any running poll/timer on unmount (e.g. navigating away while queued).
  useEffect(() => () => stopQuickmatchTimers(), []);

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

  // ── Quick Match — auto-pairs with a free player instead of a code ──────
  async function handleQuickmatchStart() {
    setBusy(true);
    setError(null);
    setQueuedSeconds(0);
    try {
      const result = await matchApi.quickmatchJoin(token);
      if (result.status === "matched" && result.match) {
        onMatched(result.match);
        return;
      }
      // Still waiting — start polling for a pairing.
      setMode("quickmatching");
      setQueueSize(result.queue_size);
      secondsRef.current = setInterval(() => setQueuedSeconds((s) => s + 1), 1000);
      pollRef.current = setInterval(async () => {
        try {
          const status = await matchApi.quickmatchStatus(token);
          if (status.status === "matched" && status.match) {
            stopQuickmatchTimers();
            onMatched(status.match);
          } else {
            setQueueSize(status.queue_size);
          }
        } catch {
          // Transient network hiccup — the next poll tick will retry.
        }
      }, QUICKMATCH_POLL_MS);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Quick Match abhi available nahi hai.");
    } finally {
      setBusy(false);
    }
  }

  async function handleQuickmatchCancel() {
    stopQuickmatchTimers();
    setMode("idle");
    try {
      await matchApi.quickmatchLeave(token);
    } catch {
      // Best-effort — worst case the entry expires server-side on its own.
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

      {mode === "idle" && (
        <div className="mb-4 grid gap-2">
          <button
            type="button"
            onClick={handleQuickmatchStart}
            disabled={busy}
            className="px-3 py-3 text-xs font-black uppercase disabled:opacity-50"
            style={{ background: "var(--pt-green)", color: "#fff" }}
          >
            ⚡ Quick Match — Free Khiladi Dhoondein
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleCreate}
              disabled={busy}
              className="flex-1 px-3 py-2 text-xs font-bold uppercase disabled:opacity-50"
              style={{ background: "var(--pt-saffron)", color: "#fff" }}
            >
              🏙️ Naya Match Banayein
            </button>
            <button
              type="button"
              onClick={() => setMode("joining")}
              disabled={busy}
              className="flex-1 px-3 py-2 text-xs font-bold uppercase disabled:opacity-50"
              style={{ border: "1px solid var(--pt-line)", color: "var(--pt-muted)" }}
            >
              🔑 Code se Join Karein
            </button>
          </div>
        </div>
      )}

      {mode === "quickmatching" && (
        <div className="mb-4 p-4 text-center" style={{ border: "1px dashed var(--pt-green)" }}>
          <div className="flex items-center justify-center gap-2">
            <span className="h-2 w-2 animate-pulse rounded-full" style={{ background: "var(--pt-green)" }} />
            <div className="text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>
              Khiladi dhoonda ja raha hai…
            </div>
          </div>
          <div className="my-2 text-2xl font-black" style={{ color: "var(--pt-green)" }}>
            {queuedSeconds}s
          </div>
          <div className="text-[10px]" style={{ color: "var(--pt-muted)" }}>
            {queueSize > 0 ? `${queueSize} khiladi queue mein` : "Koi doosra khiladi milte hi match shuru ho jayega."}
          </div>
          <button
            type="button"
            onClick={handleQuickmatchCancel}
            className="mt-3 px-3 py-1.5 text-[11px] font-bold uppercase"
            style={{ border: "1px solid var(--pt-line)", color: "var(--pt-muted)" }}
          >
            Cancel
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
