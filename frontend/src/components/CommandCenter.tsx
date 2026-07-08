"use client";

/**
 * CommandCenter — the multi-city "Bloomberg Terminal of Politics".
 *
 * Left sidebar = Global Map: every city in the campaign, colour-coded
 * green (you're Incumbent) / red (you're Opposition), with warning icons
 * (⚠️ Strike, 🚨 Audit in Progress, 🛑 Emergency) and a phase badge showing
 * when its polling day arrives. Clicking a city swaps the main dashboard's
 * context instantly. "Split-Screen" opens a second dashboard pane so you
 * can watch one city while acting in another.
 *
 * This talks to the /api/campaign/* endpoints in campaignApi.ts — see
 * backend/app/services/campaign_engine.py for the mechanics themselves
 * (Black Money Pipeline, Staggered Phases, Asymmetric Retaliation).
 */

import { useCallback, useEffect, useState } from "react";
import { CampaignCityInfo, CampaignState, campaignApi } from "@/lib/campaignApi";

type Props = {
  campaignId: string;
  playerId: string;
  pollMs?: number;
};

const POLL_DEFAULT = 5000;

export default function CommandCenter({ campaignId, playerId, pollMs = POLL_DEFAULT }: Props) {
  const [state, setState] = useState<CampaignState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedCityId, setSelectedCityId] = useState<string | null>(null);
  const [splitCityId, setSplitCityId] = useState<string | null>(null);
  const [splitScreen, setSplitScreen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const fresh = await campaignApi.state(campaignId);
      setState(fresh);
      setError(null);
      setSelectedCityId((prev) => prev ?? fresh.cities[0]?.city_id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load campaign state.");
    }
  }, [campaignId]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, pollMs);
    return () => clearInterval(id);
  }, [refresh, pollMs]);

  async function runAction<T>(fn: () => Promise<T>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!state) {
    return (
      <div className="p-6 text-xs" style={{ color: "var(--pt-muted)" }}>
        {error ?? "Loading Command Center…"}
      </div>
    );
  }

  const myAccount = state.accounts.find((a) => a.player_id === playerId);
  const selectedCity = state.cities.find((c) => c.city_id === selectedCityId) ?? null;
  const splitCity = state.cities.find((c) => c.city_id === splitCityId) ?? null;

  return (
    <div className="flex h-full min-h-[640px] w-full" style={{ background: "var(--pt-ink)", color: "var(--pt-white)" }}>
      {/* ── Global Map sidebar ── */}
      <aside className="w-72 shrink-0 border-r" style={{ borderColor: "var(--pt-line)", background: "var(--pt-panel)" }}>
        <div className="border-b p-3" style={{ borderColor: "var(--pt-line)" }}>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--pt-muted)" }}>
            Global Map
          </div>
          <div className="text-sm font-black">Phase {state.current_phase} / {state.total_phases}</div>
        </div>

        <div className="ledger-scroll overflow-y-auto" style={{ maxHeight: 460 }}>
          {state.cities.map((city) => (
            <CityRow
              key={city.city_id}
              city={city}
              playerId={playerId}
              selected={city.city_id === selectedCityId}
              onClick={() => setSelectedCityId(city.city_id)}
              onSplitClick={splitScreen ? () => setSplitCityId(city.city_id) : undefined}
            />
          ))}
        </div>

        <div className="border-t p-3" style={{ borderColor: "var(--pt-line)" }}>
          <button
            type="button"
            onClick={() => setSplitScreen((v) => !v)}
            className="w-full px-2 py-2 text-[11px] font-bold uppercase"
            style={{
              background: splitScreen ? "var(--pt-saffron)" : "transparent",
              border: "1px solid var(--pt-saffron)",
              color: splitScreen ? "#fff" : "var(--pt-saffron)",
            }}
          >
            {splitScreen ? "Exit Split-Screen" : "🖥️ Split-Screen Mode"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => runAction(() => campaignApi.advancePhase(campaignId, playerId))}
            className="mt-2 w-full px-2 py-2 text-[11px] font-bold uppercase"
            style={{ background: "var(--pt-wheel)", color: "#fff" }}
          >
            📅 Advance to Next Phase
          </button>
        </div>
      </aside>

      {/* ── Main dashboard(s) ── */}
      <main className="flex flex-1 flex-col overflow-hidden">
        {error && (
          <div className="px-4 py-2 text-[11px]" style={{ borderBottom: "1px solid var(--pt-red)", color: "var(--pt-red-lt)" }}>
            {error}
          </div>
        )}

        <div className="flex flex-1 overflow-hidden">
          <CityDashboard
            city={selectedCity}
            playerId={playerId}
            campaignId={campaignId}
            myOffshoreBalance={myAccount?.balance ?? 0}
            myAccountFrozen={!!myAccount?.frozen_until}
            busy={busy}
            runAction={runAction}
            allCities={state.cities}
          />
          {splitScreen && <div className="w-px shrink-0" style={{ background: "var(--pt-line)" }} />}
          {splitScreen && (
            <CityDashboard
              city={splitCity}
              playerId={playerId}
              campaignId={campaignId}
              myOffshoreBalance={myAccount?.balance ?? 0}
              myAccountFrozen={!!myAccount?.frozen_until}
              busy={busy}
              runAction={runAction}
              allCities={state.cities}
              compact
            />
          )}
        </div>

        {/* Live headline ticker */}
        <div className="border-t p-2" style={{ borderColor: "var(--pt-line)", background: "var(--pt-panel)" }}>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--pt-muted)" }}>
            Wire Desk
          </div>
          <div className="ledger-scroll overflow-y-auto text-[11px]" style={{ maxHeight: 90 }}>
            {state.headlines
              .slice()
              .reverse()
              .map((h, i) => (
                <div key={i} className="py-0.5" style={{ color: "var(--pt-white)" }}>
                  {h}
                </div>
              ))}
          </div>
        </div>
      </main>
    </div>
  );
}

// ── Sidebar row ────────────────────────────────────────────────────────

function CityRow({
  city,
  playerId,
  selected,
  onClick,
  onSplitClick,
}: {
  city: CampaignCityInfo;
  playerId: string;
  selected: boolean;
  onClick: () => void;
  onSplitClick?: () => void;
}) {
  const role = city.incumbent_player_id === playerId ? "Incumbent" : city.opposition_player_id === playerId ? "Opposition" : null;
  const roleColor = role === "Incumbent" ? "var(--pt-green)" : role === "Opposition" ? "var(--pt-red)" : "var(--pt-line)";

  return (
    <div
      onClick={onClick}
      onDoubleClick={onSplitClick}
      className="cursor-pointer border-b px-3 py-2 text-xs"
      style={{
        borderColor: "var(--pt-line)",
        background: selected ? "var(--pt-panel-hi)" : "transparent",
      }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: roleColor }} />
          <span className="font-bold">{city.name}</span>
        </div>
        <span className="text-[10px]" style={{ color: "var(--pt-muted)" }}>
          Ph.{city.phase}
        </span>
      </div>
      <div className="mt-0.5 flex items-center justify-between text-[10px]" style={{ color: "var(--pt-muted)" }}>
        <span>
          {role ?? "—"}
          {city.election_completed ? " · decided" : city.voting_open ? " · polling open" : " · not yet"}
        </span>
        <span>{city.warnings.join(" ")}</span>
      </div>
      {onSplitClick && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onSplitClick();
          }}
          className="mt-1 text-[10px] underline"
          style={{ color: "var(--pt-wheel-lt)" }}
        >
          open in split pane
        </button>
      )}
    </div>
  );
}

// ── Main dashboard panel for one city ─────────────────────────────────

function CityDashboard({
  city,
  playerId,
  campaignId,
  myOffshoreBalance,
  myAccountFrozen,
  busy,
  runAction,
  allCities,
  compact,
}: {
  city: CampaignCityInfo | null;
  playerId: string;
  campaignId: string;
  myOffshoreBalance: number;
  myAccountFrozen: boolean;
  busy: boolean;
  runAction: <T>(fn: () => Promise<T>) => Promise<void>;
  allCities: CampaignCityInfo[];
  compact?: boolean;
}) {
  const [siphonBudget, setSiphonBudget] = useState(500_000);
  const [siphonPercent, setSiphonPercent] = useState(35);
  const [fundAmount, setFundAmount] = useState(100_000);

  if (!city) {
    return (
      <div className="flex-1 p-4 text-xs" style={{ color: "var(--pt-muted)" }}>
        Select a city.
      </div>
    );
  }

  const isIncumbent = city.incumbent_player_id === playerId;
  const isOpposition = city.opposition_player_id === playerId;
  const label = isIncumbent ? "Sattadheen (Incumbent) War Room" : isOpposition ? "Vipaksh (Opposition) War Room" : "Spectating";

  return (
    <div className="ledger-scroll flex-1 overflow-y-auto p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <div className="text-lg font-black">{city.name}</div>
          <div className="text-[11px]" style={{ color: isIncumbent ? "var(--pt-green-lt)" : "var(--pt-red-lt)" }}>
            {label}
          </div>
        </div>
        <div className="text-[10px]" style={{ color: "var(--pt-muted)" }}>
          Incumbent: {city.incumbent_username} · Opposition: {city.opposition_username}
        </div>
      </div>

      {city.momentum_trust_buff > 0 && (
        <div className="mb-3 px-2 py-1 text-[11px]" style={{ border: "1px solid var(--pt-gold)", color: "var(--pt-gold)" }}>
          🌊 National Wave momentum: +{city.momentum_trust_buff} base Trust from an earlier phase win.
        </div>
      )}

      {/* Incumbent tools: siphon + retaliation */}
      {isIncumbent && !compact && (
        <section className="mb-4 border p-3" style={{ borderColor: "var(--pt-line)" }}>
          <div className="mb-2 text-[11px] font-bold uppercase" style={{ color: "var(--pt-gold)" }}>
            💰 Commission Project (skim into Offshore Account)
          </div>
          <div className="mb-2 flex gap-2 text-[11px]">
            <label className="flex-1">
              Budget
              <input
                type="number"
                value={siphonBudget}
                onChange={(e) => setSiphonBudget(Number(e.target.value))}
                className="mt-1 w-full bg-transparent px-2 py-1"
                style={{ border: "1px solid var(--pt-line)" }}
              />
            </label>
            <label className="flex-1">
              Siphon %
              <input
                type="number"
                value={siphonPercent}
                min={0}
                max={80}
                onChange={(e) => setSiphonPercent(Number(e.target.value))}
                className="mt-1 w-full bg-transparent px-2 py-1"
                style={{ border: "1px solid var(--pt-line)" }}
              />
            </label>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              runAction(() =>
                campaignApi.siphonConstruct(campaignId, playerId, city.city_id, {
                  role: "Incumbent",
                  player_username: city.incumbent_username,
                  block_type: "Industrial",
                  name: "Grand Highway",
                  budget: siphonBudget,
                  siphon_percent: siphonPercent,
                }),
              )
            }
            className="w-full px-2 py-2 text-[11px] font-bold uppercase"
            style={{ background: "var(--pt-gold)", color: "#1a1200" }}
          >
            Build &amp; Skim
          </button>

          <div className="mt-3 border-t pt-3" style={{ borderColor: "var(--pt-line)" }}>
            <div className="mb-1 text-[11px] font-bold uppercase" style={{ color: "var(--pt-red-lt)" }}>
              🚔 Arrest Opposition Leaders
            </div>
            <p className="mb-2 text-[10px]" style={{ color: "var(--pt-muted)" }}>
              Docks the rival&apos;s Influence Points campaign-wide for 5 minutes. Mutually assured destruction.
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={() => runAction(() => campaignApi.retaliate(campaignId, playerId, city.city_id))}
              className="w-full px-2 py-2 text-[11px] font-bold uppercase"
              style={{ background: "var(--pt-red)", color: "#fff" }}
            >
              Deploy State Machinery
            </button>
          </div>
        </section>
      )}

      {/* Opposition tools: fund + expose */}
      {isOpposition && !compact && (
        <section className="mb-4 border p-3" style={{ borderColor: "var(--pt-line)" }}>
          <div className="mb-2 text-[11px] font-bold uppercase" style={{ color: "var(--pt-red-lt)" }}>
            🕵️ Fund Opposition from Offshore Account
          </div>
          <p className="mb-2 text-[10px]" style={{ color: "var(--pt-muted)" }}>
            Your Offshore Account (built from a city where you&apos;re Incumbent): ₹{myOffshoreBalance.toLocaleString()}
            {myAccountFrozen && <span style={{ color: "var(--pt-red-lt)" }}> — FROZEN (exposed)</span>}
          </p>
          <div className="mb-2 flex gap-2 text-[11px]">
            <input
              type="number"
              value={fundAmount}
              onChange={(e) => setFundAmount(Number(e.target.value))}
              className="flex-1 bg-transparent px-2 py-1"
              style={{ border: "1px solid var(--pt-line)" }}
            />
            <button
              type="button"
              disabled={busy || myAccountFrozen}
              onClick={() => runAction(() => campaignApi.fundOpposition(campaignId, playerId, city.city_id, fundAmount))}
              className="px-3 py-1 text-[11px] font-bold uppercase"
              style={{ background: "var(--pt-red)", color: "#fff" }}
            >
              Fund Riots/Strikes
            </button>
          </div>

          <div className="mt-3 border-t pt-3" style={{ borderColor: "var(--pt-line)" }}>
            <div className="mb-1 text-[11px] font-bold uppercase" style={{ color: "var(--pt-wheel-lt)" }}>
              🚨 Audit &amp; Expose the Pipeline
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => runAction(() => campaignApi.exposeLaundering(campaignId, playerId, city.city_id))}
              className="w-full px-2 py-2 text-[11px] font-bold uppercase"
              style={{ background: "var(--pt-wheel)", color: "#fff" }}
            >
              Expose Offshore Laundering
            </button>
          </div>
        </section>
      )}

      {/* Elections */}
      {isIncumbent && city.voting_open && !city.election_completed && (
        <button
          type="button"
          disabled={busy}
          onClick={() => runAction(() => campaignApi.runCityElection(campaignId, playerId, city.city_id))}
          className="w-full px-2 py-2 text-[11px] font-bold uppercase"
          style={{ background: "var(--pt-saffron)", color: "#fff" }}
        >
          🗳️ Call Election in {city.name}
        </button>
      )}
      {city.election_completed && (
        <div className="px-2 py-2 text-[11px]" style={{ border: "1px solid var(--pt-line)", color: "var(--pt-muted)" }}>
          Decided — winner: {city.winner_player_id === city.incumbent_player_id ? city.incumbent_username : city.opposition_username}
        </div>
      )}

      {!compact && (
        <div className="mt-4 text-[10px]" style={{ color: "var(--pt-muted)" }}>
          Other cities in campaign: {allCities.filter((c) => c.city_id !== city.city_id).map((c) => c.name).join(", ")}
        </div>
      )}
    </div>
  );
}
