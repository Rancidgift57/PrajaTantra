"use client";

import { useState } from "react";
import CommandCenter from "@/components/CommandCenter";
import { CampaignState, campaignApi } from "@/lib/campaignApi";

function randomPlayerId() {
  return `player_${Math.random().toString(36).slice(2, 10)}`;
}

export default function CampaignPage() {
  const [playerId] = useState(randomPlayerId);
  const [username, setUsername] = useState("Mayor_Nikhil");
  const [joinCode, setJoinCode] = useState("");
  const [campaign, setCampaign] = useState<CampaignState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleCreate() {
    setBusy(true);
    setError(null);
    try {
      const state = await campaignApi.create(playerId, username, ["Bengaluru", "Mumbai", "Chennai", "Delhi"]);
      setCampaign(state);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create campaign.");
    } finally {
      setBusy(false);
    }
  }

  async function handleJoin() {
    setBusy(true);
    setError(null);
    try {
      const state = await campaignApi.join(playerId, joinCode.trim().toUpperCase(), username);
      setCampaign(state);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not join campaign.");
    } finally {
      setBusy(false);
    }
  }

  if (campaign) {
    return <CommandCenter campaignId={campaign.campaign_id} playerId={playerId} />;
  }

  return (
    <div
      className="mx-auto mt-16 max-w-md p-6"
      style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)", color: "var(--pt-white)" }}
    >
      <div className="mb-1 font-black text-lg">Multi-City Campaign</div>
      <div className="mb-5 text-[11px]" style={{ color: "var(--pt-muted)" }}>
        Start a 4-city campaign (Phase 1: Bengaluru · Phase 2: Mumbai + Chennai · Phase 3: Delhi), or join one with a
        code. Roles flip city-to-city — Incumbent somewhere means Opposition somewhere else.
      </div>

      {error && (
        <div className="mb-4 px-3 py-2 text-[11px]" style={{ border: "1px solid var(--pt-red)", color: "var(--pt-red-lt)" }}>
          {error}
        </div>
      )}

      <label className="mb-3 block text-[11px]">
        Your name
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="mt-1 w-full bg-transparent px-2 py-1"
          style={{ border: "1px solid var(--pt-line)" }}
        />
      </label>

      <button
        type="button"
        disabled={busy}
        onClick={handleCreate}
        className="mb-3 w-full px-3 py-2 text-xs font-bold uppercase"
        style={{ background: "var(--pt-saffron)", color: "#fff" }}
      >
        🗺️ Start New Campaign
      </button>

      <div className="mb-2 flex gap-2">
        <input
          value={joinCode}
          onChange={(e) => setJoinCode(e.target.value)}
          placeholder="JOIN CODE"
          className="flex-1 bg-transparent px-2 py-1 text-xs uppercase"
          style={{ border: "1px solid var(--pt-line)" }}
        />
        <button
          type="button"
          disabled={busy || !joinCode.trim()}
          onClick={handleJoin}
          className="px-3 py-2 text-xs font-bold uppercase"
          style={{ background: "var(--pt-wheel)", color: "#fff" }}
        >
          Join
        </button>
      </div>
    </div>
  );
}
