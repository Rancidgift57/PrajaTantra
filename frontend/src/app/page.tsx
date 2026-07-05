"use client";

import {
  Banknote,
  Bolt,
  Building2,
  Factory,
  FileSearch,
  Gavel,
  Globe2,
  HandCoins,
  Landmark,
  Megaphone,
  Radio,
  Satellite,
  ShieldAlert,
  Siren,
  Stethoscope,
  UsersRound,
  Vote,
  Scale,
  Newspaper,
  AlertTriangle,
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import AuthGate from "@/components/AuthGate";
import CityDevelopment from "@/components/CityDevelopment";
import CityMap from "@/components/CityMap";
import Leaderboard from "@/components/Leaderboard";
import MatchLobby from "@/components/MatchLobby";
import LiveEventFeed from "@/components/LiveEventFeed";
import SeatMap from "@/components/SeatMap";
import StreakBadge, { recordMatchResult } from "@/components/StreakBadge";

import { matchApi, MatchInfo } from "@/lib/matchApi";
import { useMatchSocket } from "@/lib/useMatchSocket";
import { createMatchDevClient } from "@/lib/matchApiAdapter";

import {
  api,
  AuditResponse,
  AuthResponse,
  CountingRoundResult,
  ElectionResponse,
  GraphEdge,
  GraphNode,
  InfrastructureBlock,
  PlayerProfile,
  PlayerRole,
  PortfolioType,
  ScamResponse,
  SovereignState,
  TenRoundSimulationResponse,
} from "@/lib/api";

// ─── Indian political context strings ─────────────────────────────────────
const initialManifesto =
  "हम औद्योगिक कर में 2% की वृद्धि करेंगे, ऑडिटेड स्वास्थ्य बॉन्ड जारी करेंगे, और मील-पत्थर अनुदान के माध्यम से सड़क खरीद को चरणबद्ध करेंगे। पहली ट्रेज़री रिलीज़ अस्पताल बेड, प्रशिक्षुता और यातायात मरम्मत को निधि देती है।\n\nWe will raise industrial tax by 2%, issue audited health bonds, and phase road procurement through milestone grants. Treasury release one funds hospital beds, apprenticeships, and congestion repairs — every vendor contract published for Jan Lokpal audit.";

const initialSpeech =
  "Sabka Saath, Sabka Vikas — our mandate is disciplined growth: build health capacity, create rozgaar, protect clean roads, and publish every ठेका. The current sarkar failed karyakartas with waste, hidden vendors, and scam-linked spending. Vote for audited delivery, Jan Vishwas, and stronger exports. Jai Hind!";

const blockIcons: Record<PortfolioType, ReactNode> = {
  Industrial: <Factory className="h-4 w-4" />,
  Social:     <Stethoscope className="h-4 w-4" />,
  Strategic:  <Satellite className="h-4 w-4" />,
};

// ─── Indian labels for portfolio types ────────────────────────────────────
const blockLabels: Record<PortfolioType, { name: string; hindi: string }> = {
  Industrial: { name: "Industrial",  hindi: "उद्योग" },
  Social:     { name: "Social",      hindi: "समाज" },
  Strategic:  { name: "Strategic",   hindi: "रणनीति" },
};

// Portfolio project names — Indian-flavoured
function projectNameFor(blockType: PortfolioType): string {
  return blockType === "Industrial"
    ? "MSME Export Corridor"
    : blockType === "Social"
    ? "Ayushman Lok Grid"
    : "ISRO Orbital Mission";
}

// ─── Indian city IDs used in the grant call ───────────────────────────────
const CITY_PAIRS: Record<string, { mayor: string; city: string }> = {
  "MUM_01": { mayor: "CM_Fadnavis", city: "MUM_01" },
  "DEL_01": { mayor: "CM_Kejriwal", city: "DEL_01" },
  "BLR_01": { mayor: "CM_Siddaramaiah", city: "BLR_01" },
};

function Dashboard({
  player,
  token,
  matchId,
  onCityRenamed,
  onLogout,
  onLeaveMatch,
}: {
  player: PlayerProfile;
  token: string;
  matchId: string;
  onCityRenamed: (newName: string) => void;
  onLogout: () => void;
  onLeaveMatch: () => void;
}) {
  // ── Live match sync ──────────────────────────────────────────────────
  // state comes from the WebSocket broadcast (see lib/useMatchSocket.ts):
  // every action either player takes — build, strike, leak, grant — pushes
  // a fresh SovereignState to BOTH clients the instant it happens. `role`
  // is derived from the seat the server assigned this player_id, never
  // from a client-side toggle.
  const { state: socketState, match, connected, opponentOnline } = useMatchSocket(matchId, token);
  const [state, setState] = useState<SovereignState | null>(null);
  const role: PlayerRole = match?.your_role ?? "Incumbent";
  const devClient = useMemo(() => createMatchDevClient(matchId, token), [matchId, token]);

  useEffect(() => {
    if (socketState) setState(socketState);
  }, [socketState]);

  const [blockType, setBlockType]     = useState<PortfolioType>("Industrial");
  const [budget, setBudget]           = useState(420_000);
  const [siphon, setSiphon]           = useState(15);
  const [layerDepth, setLayerDepth]   = useState(1);
  const [auditLevel, setAuditLevel]   = useState(2);
  const [targetBlockId, setTargetBlockId] = useState("IND-001");
  const [scam, setScam]               = useState<ScamResponse | null>(null);
  const [audit, setAudit]             = useState<AuditResponse | null>(null);
  const [election, setElection]       = useState<ElectionResponse | null>(null);
  const [simulation, setSimulation]   = useState<TenRoundSimulationResponse | null>(null);
  const [consecutiveTerms, setConsecutiveTerms] = useState(1);
  const [manifesto, setManifesto]     = useState(initialManifesto);
  const [speech, setSpeech]           = useState(initialSpeech);
  const [busyAction, setBusyAction]   = useState<string | null>(null);
  const [flash, setFlash]             = useState(`🇮🇳  ${player.city_name} — Niyantran Kaksha online.`);
  const [renaming, setRenaming]       = useState(false);
  const [cityNameDraft, setCityNameDraft] = useState(player.city_name);

  // Seed the target block picker the first time state arrives.
  useEffect(() => {
    if (state && !targetBlockId) setTargetBlockId(state.blocks[0]?.id ?? "");
  }, [state, targetBlockId]);

  // Note: leaderboard stat sync (gold/troops/owned%) happens server-side
  // automatically whenever city state changes — see SETUP.md "Leaderboard
  // sync" section for how to wire a real-time push if you add a DB later.

  async function submitCityRename() {
    if (!cityNameDraft.trim() || cityNameDraft === player.city_name) {
      setRenaming(false);
      return;
    }
    setBusyAction("rename");
    try {
      const response = await api.renameCity(token, cityNameDraft.trim());
      onCityRenamed(response.city_name);
      setFlash(response.message);
      setRenaming(false);
    } catch (error) {
      setFlash(messageFromError(error, "Naam badalna asafal raha."));
    } finally {
      setBusyAction(null);
    }
  }

  const projectName   = projectNameFor(blockType);
  const activeNodes   = audit?.paths[0]?.nodes ?? scam?.nodes ?? [];
  const activeEdges   = audit?.paths[0]?.edges ?? scam?.edges ?? [];
  const stats         = state?.city;
  const activeTarget  = state?.blocks.find((b) => b.id === targetBlockId) ?? state?.blocks[0];
  const netTick = useMemo(
    () => (state?.blocks ?? []).reduce((sum, b) => sum + b.gold_per_tick - b.maintenance, 0),
    [state?.blocks],
  );

  // ─── Actions ────────────────────────────────────────────────────────────
  async function buildInfrastructure() {
    setBusyAction("build");
    try {
      const response = await matchApi.action<{ state: SovereignState; scam: ScamResponse; message: string }>(
        matchId,
        "construction/build",
        token,
        {
          role,
          player_username: player.username,
          block_type: blockType,
          name: projectName,
          budget,
          siphon_percent: siphon,
          layer_depth: layerDepth,
        },
      );
      setState(response.state);
      setScam(response.scam);
      setAudit(null);
      setFlash(response.message);
    } catch (error) {
      setFlash(messageFromError(error, "Yojana nirman asvikaar."));
    } finally {
      setBusyAction(null);
    }
  }

  async function runAudit(level = auditLevel) {
    setBusyAction("audit");
    try {
      const response = await api.auditProject({
        project_id: scam?.project_id,
        project_name: scam ? projectName : "Sarkaari Aspatal",
        audit_level: level,
      });
      setAudit(response);
      setAuditLevel(level);
      setFlash(
        response.corruption_detected
          ? "🚨 Saboot mil gaya — CBI file ready!"
          : response.next_upgrade_hint,
      );
    } catch (error) {
      setFlash(messageFromError(error, "Audit vifal."));
    } finally {
      setBusyAction(null);
    }
  }

  async function organizeStrike() {
    if (!activeTarget) { setFlash("Koi lakshya chunein."); return; }
    setBusyAction("strike");
    try {
      const response = await matchApi.action<{ state: SovereignState; message: string }>(
        matchId,
        "opposition/strike",
        token,
        { role, target_block_id: activeTarget.id, influence_spend: 18 },
      );
      setState(response.state);
      setFlash(response.message);
    } catch (error) {
      setFlash(messageFromError(error, "Hartal vifal."));
    } finally {
      setBusyAction(null);
    }
  }

  async function leakAudit() {
    if (!audit) { setFlash("Pehle audit karein, phir samachaar desk ko bhejein."); return; }
    setBusyAction("leak");
    try {
      const response = await matchApi.action<{ state: SovereignState; trust_damage: number; message: string }>(
        matchId,
        "opposition/leak",
        token,
        { role, audit },
      );
      setState(response.state);
      setFlash(`📰 Khabar chhap gayi — Vishwas nuksan: ${response.trust_damage}`);
    } catch (error) {
      setFlash(messageFromError(error, "Leak vifal."));
    } finally {
      setBusyAction(null);
    }
  }

  async function gradeElection() {
    setBusyAction("election");
    try {
      const city = state?.city;
      const blocks = state?.blocks ?? [];

      // ── Derive incumbent match score from actual game state ─────────────
      // Reward good governance (trust, GDP, low pollution) and punish corruption
      const trustScore     = Math.min((city?.public_trust ?? 50) / 100 * 35, 35);
      const gdpScore       = Math.min((city?.gdp ?? 0) / 15_000 * 20, 20);
      const pollutionPenalty = Math.min((city?.pollution ?? 0) / 100 * 10, 10);
      const unrestPenalty    = Math.min((city?.worker_unrest ?? 0) / 100 * 8, 8);
      const corruptionPenalty = Math.min((city?.corruption_leaks ?? 0) * 8, 24);
      const prestigeBonus  = Math.min((city?.national_prestige ?? 0) / 100 * 10, 10);
      // Social blocks built = care for the voter base
      const socialBlocks   = blocks.filter((b) => b.portfolio_type === "Social").length;
      const socialBonus    = Math.min(socialBlocks * 4, 12);
      const derivedIncumbentMatch = Math.max(10, Math.min(95,
        45 + trustScore + gdpScore - pollutionPenalty - unrestPenalty - corruptionPenalty + prestigeBonus + socialBonus
      ));

      // ── Derive opposition match score — mirrors corruption & unrest ──────
      // Opposition gets stronger exactly where the incumbent is weakest
      const leakMomentum   = Math.min((city?.corruption_leaks ?? 0) * 10, 30);
      const unrestMomentum = Math.min((city?.worker_unrest ?? 0) / 100 * 15, 15);
      const trustGap       = Math.max(0, 50 - (city?.public_trust ?? 50)) * 0.5;
      // Incumbent's consecutive-term fatigue directly boosts opposition
      const termBonus      = consecutiveTerms * 5;
      const derivedOppositionMatch = Math.max(10, Math.min(95,
        40 + leakMomentum + unrestMomentum + trustGap + termBonus
      ));

      // ── Grade the manifesto/speech first (AI-judged via HuggingFace, with
      // an offline heuristic fallback) so its trust_score can nudge seat
      // swing in the counting simulation below — manifesto quality and
      // development delivery should actually move seats, not just votes.
      const response = await api.gradeElection({
        city_stats: city,
        crises: ["pradooshan spike", "shramik asantosh", "swasthya sankat"],
        manifesto,
        speech_transcript: speech,
        consecutive_terms: consecutiveTerms,
      });
      const simResponse = await api.simulateTenRoundCounting({
        global_trust: city?.public_trust ?? 55,
        scams_exposed: city?.corruption_leaks ?? 0,
        consecutive_terms: consecutiveTerms,
        incumbent_name: state?.incumbent ?? "Sattadheen Dal",
        opposition_name: state?.opposition ?? "Vipaksh Dal",
        incumbent_match_score: derivedIncumbentMatch,
        opposition_match_score: derivedOppositionMatch,
        total_electorate: 100_000,
        total_seats: 101,
        manifesto_trust_score: response.trust_score,
      });
      setElection(response);
      setSimulation(simResponse);
      const iWon =
        (role === "Incumbent" && simResponse.winner === (state?.incumbent ?? "Sattadheen Dal")) ||
        (role === "Opposition" && simResponse.winner === (state?.opposition ?? "Vipaksh Dal"));
      recordMatchResult(iWon);
      setFlash(
        `🗳️ ${simResponse.winner} jeeta! ${simResponse.incumbent_seats}-${simResponse.opposition_seats}-${simResponse.independent_seats} seats (${simResponse.total_seats} total) · Margin ${simResponse.margin.toLocaleString("en-IN")} votes (${simResponse.margin_pct}%)`
      );
    } catch (error) {
      setFlash(messageFromError(error, "Matganak vifal."));
    } finally {
      setBusyAction(null);
    }
  }

  async function declareEmergency() {
    if (!simulation) return;
    setBusyAction("emergency");
    try {
      const response = await matchApi.action<{
        state: SovereignState;
        granted: boolean;
        seat_share_pct: number;
        message: string;
      }>(matchId, "emergency/declare", token, {
        incumbent_seats: simulation.incumbent_seats ?? 0,
        total_seats: simulation.total_seats ?? 101,
        threshold_pct: simulation.emergency_threshold_pct ?? 80,
      });
      setState(response.state);
      setFlash(`🚨 ${response.message}`);
    } catch (error) {
      setFlash(messageFromError(error, "Aapatkaal ghoshit nahi ho saka."));
    } finally {
      setBusyAction(null);
    }
  }

  async function issueGrant() {
    setBusyAction("grant");
    try {
      const response = await matchApi.action<{ state: SovereignState; message: string }>(
        matchId,
        "federal/grant",
        token,
        {
          prime_minister: "PM_Modi",
          target_city_id: "BLR_01",
          mayor_username: player.username,
          amount: 350_000,
          alignment: role === "Incumbent" ? "ally" : "rival",
        },
      );
      setState(response.state);
      setFlash(response.message);
    } catch (error) {
      setFlash(messageFromError(error, "Kendra anudan vifal."));
    } finally {
      setBusyAction(null);
    }
  }

  async function resolveTradeDuel() {
    setBusyAction("trade");
    try {
      const response = await matchApi.action<{
        state: SovereignState;
        winner: string;
        country_score: number;
        rival_score: number;
      }>(matchId, "global/trade-duel", token, {
        country_name:             "Bharatiya Gantantra",
        rival_country_name:       "Uttar Sangh",
        net_exports:              78,
        tariff_rate:              12,
        supply_chain_resilience:  66,
        rival_net_exports:        62,
        rival_tariff_rate:        22,
        rival_supply_chain_resilience: 58,
      });
      setState(response.state);
      setFlash(
        `🤝 ${response.winner} vyaapaar duel jeeta — ${response.country_score}-${response.rival_score}.`,
      );
    } catch (error) {
      setFlash(messageFromError(error, "Vyaapaar duel vifal."));
    } finally {
      setBusyAction(null);
    }
  }

  // ─── Render ─────────────────────────────────────────────────────────────
  return (
    <main className="min-h-screen" style={{ color: "var(--pt-white)" }} suppressHydrationWarning>
      {/* Tricolour top bar */}
      <div className="tricolour-bar" />

      {/* OpenFront-style floating leaderboard, top-left */}
      <Leaderboard token={token} />

      <div className="mx-auto flex w-full max-w-[1760px] flex-col gap-4 px-4 py-4 lg:px-6">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <header
          className="grid gap-4 pb-4 xl:grid-cols-[1fr_520px]"
          style={{ borderBottom: "1px solid var(--pt-line)" }}
        >
          <div>
            <div
              className="flex flex-wrap items-center gap-3 text-xs uppercase"
              style={{ color: "var(--pt-saffron)" }}
            >
              <Landmark className="h-4 w-4" />
              PrajaTantra — Loktantra Simulator
              <span
                className="px-2 py-1 text-xs"
                style={{ border: "1px solid var(--pt-line)", color: "var(--pt-muted)" }}
              >
                OpenFront Edition · भारत
              </span>
              <button
                type="button"
                onClick={onLogout}
                className="ml-auto px-2 py-1 text-xs font-bold uppercase"
                style={{ border: "1px solid var(--pt-line)", color: "var(--pt-muted)" }}
              >
                {player.username} · Logout
              </button>
            </div>
            <div className="mt-3 flex flex-wrap items-end gap-4">
              {renaming ? (
                <div className="flex items-center gap-2">
                  <input
                    autoFocus
                    value={cityNameDraft}
                    onChange={(e) => setCityNameDraft(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && submitCityRename()}
                    className="h-12 px-3 text-3xl font-black tracking-tight outline-none md:text-4xl"
                    style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-saffron)", color: "var(--pt-white)" }}
                  />
                  <button
                    type="button"
                    onClick={submitCityRename}
                    disabled={busyAction === "rename"}
                    className="h-10 px-3 text-xs font-black uppercase"
                    style={{ background: "var(--pt-saffron)", color: "#fff" }}
                  >
                    Save
                  </button>
                </div>
              ) : (
                <h1
                  className="cursor-pointer text-3xl font-black tracking-tight transition-opacity hover:opacity-80 md:text-5xl"
                  title="Shehar ka naam badlein"
                  onClick={() => { setCityNameDraft(player.city_name); setRenaming(true); }}
                >
                  {player.city_name} <span style={{ color: "var(--pt-muted)", fontSize: "0.5em" }}>✎</span>
                </h1>
              )}
              <div className="text-sm" style={{ color: "var(--pt-muted)" }}>
                Mantri Mandal Satra {state?.cycle_day ?? 4}/7
              </div>
            </div>
            {/* Ticker news strip — static key forces full remount on headline change,
                preventing React text-node reconciliation crashes from browser extensions */}
            <NewsTicker headlines={state?.headlines ?? []} />
          </div>
          <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <SeatBadge role={role} match={match} connected={connected} opponentOnline={opponentOnline} onLeaveMatch={onLeaveMatch} />
            <FlashPanel flash={flash} />
          </div>
        </header>

        {/* ── Streak / rank strip ─────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <StreakBadge />
          <span className="text-[10px]" style={{ color: "var(--pt-muted)" }}>
            Match #{matchId.slice(0, 8)} · Code {match?.join_code ?? "—"}
          </span>
        </div>

        <LiveEventFeed headlines={state?.headlines ?? []} />

        {/* ── KPI Metrics ─────────────────────────────────────────────────── */}
        <section className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Metric label="Kosh (₹)"      hindi="खज़ाना" value={formatCrore(stats?.treasury ?? 0)}          tone="var(--pt-gold)" />
          <Metric label="GDP"            hindi="सकल घरेलू उत्पाद" value={formatCrore(stats?.gdp ?? 0)}   tone="var(--pt-green-lt)" />
          <Metric label="Jan Vishwas"    hindi="जन विश्वास" value={`${stats?.public_trust ?? 0}`}         tone="var(--pt-wheel-lt)" />
          <Metric label="Pradooshan"     hindi="प्रदूषण" value={`${stats?.pollution ?? 0}`}               tone="var(--pt-red-lt)" />
          <Metric label="Shramik Asant." hindi="श्रमिक असंतोष" value={`${stats?.worker_unrest ?? 0}`}    tone="var(--pt-red-lt)" />
          <Metric label="Rashtriya Gaurav" hindi="राष्ट्रीय गौरव" value={`${stats?.national_prestige ?? 0}`} tone="var(--pt-saffron)" />
        </section>

        {/* ── Main 3-column ─────────────────────────────────────────────── */}
        <section className="grid gap-4 xl:grid-cols-[420px_1fr_410px]">

          {/* Construction — सरकारी योजना */}
          <Panel
            title="Sarkari Yojana"
            subtitle="सरकारी योजना"
            icon={<Building2 className="h-5 w-5" />}
            accentColor="var(--pt-saffron)"
            locked={role !== "Incumbent"}
            lockedLabel="विपक्ष — Locked"
          >
            <Segmented
              value={blockType}
              options={["Industrial", "Social", "Strategic"]}
              onChange={(v) => setBlockType(v as PortfolioType)}
            />
            <div className="mt-4 grid gap-3">
              <Slider
                label="Budget (₹)"
                hindi="बजट"
                value={budget}
                min={180_000} max={1_600_000} step={20_000}
                onChange={setBudget}
                accentColor="var(--pt-saffron)"
                format={formatCrore}
              />
              <Slider
                label="Corruption Siphon"
                hindi="भ्रष्टाचार"
                value={siphon}
                min={0} max={80} step={5}
                suffix="%"
                onChange={setSiphon}
                accentColor="var(--pt-red)"
                format={(v) => `${v}%`}
              />
              <Slider
                label="Network Layers"
                hindi="परतें"
                value={layerDepth}
                min={1} max={6} step={1}
                onChange={setLayerDepth}
                accentColor="var(--pt-wheel-lt)"
                format={(v) => `${v}`}
              />
            </div>
            <ImpactPreview blockType={blockType} budget={budget} siphon={siphon} />
            <button
              type="button"
              onClick={buildInfrastructure}
              disabled={busyAction === "build" || role !== "Incumbent"}
              className="mt-4 flex h-12 w-full items-center justify-center gap-2 font-black disabled:cursor-not-allowed disabled:opacity-40"
              style={{
                background: "var(--pt-saffron)",
                border: "1px solid var(--pt-saffron)",
                color: "#fff",
                letterSpacing: "0.05em",
              }}
            >
              <HandCoins className="h-5 w-5" />
              {busyAction === "build" ? "Nirmaan Ho Raha Hai…" : "Yojana Laagu Karein"}
            </button>
          </Panel>

          {/* City Dashboard — विधानसभा क्षेत्र */}
          <Panel
            title="Vidhansabha Kshetra"
            subtitle="विधानसभा क्षेत्र"
            icon={<Landmark className="h-5 w-5" />}
            accentColor="var(--pt-wheel-lt)"
            fill
          >
            <div className="grid gap-3 lg:grid-cols-3">
              {(state?.blocks ?? []).map((block) => (
                <BlockTile
                  key={block.id}
                  block={block}
                  selected={block.id === targetBlockId}
                  onSelect={() => setTargetBlockId(block.id)}
                />
              ))}
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <LedgerStat label="Net Aay/Satra"    value={formatCrore(netTick)}              accent="var(--pt-gold)" />
              <LedgerStat label="Prabhav Ank (IP)"  value={`${state?.influence_points ?? 0}`} accent="var(--pt-saffron)" />
              <LedgerStat label="Audit Sujhaav"     value={`Level ${auditLevel}`}             accent="var(--pt-wheel-lt)" />
            </div>
          </Panel>

          {/* War Room — विपक्ष का अखाड़ा */}
          <Panel
            title="Vipaksh Akhada"
            subtitle="विपक्ष का अखाड़ा"
            icon={<ShieldAlert className="h-5 w-5" />}
            accentColor="var(--pt-red)"
            locked={role !== "Opposition"}
            lockedLabel="सत्ता पक्ष — Locked"
          >
            <select
              value={targetBlockId}
              onChange={(e) => setTargetBlockId(e.target.value)}
              className="h-11 w-full px-3 text-sm outline-none"
              style={{
                background: "var(--pt-ink)",
                border: "1px solid var(--pt-line)",
                color: "var(--pt-white)",
              }}
            >
              {(state?.blocks ?? []).map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </select>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <ActionBtn
                onClick={organizeStrike}
                disabled={busyAction === "strike" || role !== "Opposition"}
                bg="var(--pt-red)" color="#fff"
                icon={<Siren className="h-4 w-4" />}
                label="Hartal"
                busy={busyAction === "strike"}
                busyLabel="Roka Ja Raha…"
              />
              <ActionBtn
                onClick={leakAudit}
                disabled={busyAction === "leak" || role !== "Opposition"}
                bg="var(--pt-gold)" color="#0C0F14"
                icon={<Radio className="h-4 w-4" />}
                label="Press Leak"
                busy={busyAction === "leak"}
                busyLabel="Chhap Raha…"
              />
            </div>
            <div
              className="mt-4 p-3"
              style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)" }}
            >
              <div className="text-xs uppercase" style={{ color: "var(--pt-muted)" }}>Lakshya</div>
              <div className="mt-1 text-sm font-bold">{activeTarget?.name ?? "Koi lakshya nahi"}</div>
              <div className="mt-2 text-xs" style={{ color: "var(--pt-muted)" }}>
                Aay {formatCrore(activeTarget?.gold_per_tick ?? 0)} · Asantosh {activeTarget?.unrest_delta ?? 0}
              </div>
            </div>
          </Panel>
        </section>

        {/* ── City Development (Buildings + Schemes) ──────────────────── */}
        <section
          className="p-4"
          style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}
        >
          <div
            className="mb-4 flex items-center gap-2 pb-3"
            style={{ borderBottom: "1px solid var(--pt-line)" }}
          >
            <span style={{ color: "var(--pt-saffron)", fontSize: "1.1rem" }}>🏙️</span>
            <div>
              <div className="font-black text-sm">Shehar Vikas</div>
              <div className="text-[10px]" style={{ color: "var(--pt-muted)" }}>शहर विकास — City Development</div>
            </div>
            <span className="ml-auto text-[10px] px-2 py-1" style={{ border: "1px solid var(--pt-saffron)", color: "var(--pt-saffron)" }}>
              8 Buildings · 6 Schemes
            </span>
          </div>
          <CityDevelopment
            role={role}
            playerUsername={player.username}
            apiClient={devClient}
            onStateUpdate={(newState) => setState(newState)}
            onFlash={setFlash}
          />
        </section>

        {/* ── City Map (Zoned Grid Planner) ───────────────────────────── */}
        <section
          className="p-4"
          style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}
        >
          <div
            className="mb-4 flex items-center gap-2 pb-3"
            style={{ borderBottom: "1px solid var(--pt-line)" }}
          >
            <span style={{ color: "var(--pt-saffron)", fontSize: "1.1rem" }}>🗺️</span>
            <div>
              <div className="font-black text-sm">Shehar Naksha</div>
              <div className="text-[10px]" style={{ color: "var(--pt-muted)" }}>शहर नक्शा — City Map</div>
            </div>
            <span className="ml-auto text-[10px] px-2 py-1" style={{ border: "1px solid var(--pt-saffron)", color: "var(--pt-saffron)" }}>
              8×8 Zoned Grid · Bengaluru
            </span>
          </div>
          <CityMap
            role={role}
            playerUsername={player.username}
            cityState={state}
            apiClient={devClient}
            onStateUpdate={(newState) => setState(newState)}
            onFlash={setFlash}
          />
        </section>

        {/* ── Graph + Audit ────────────────────────────────────────────── */}
        <section className="grid gap-4 xl:grid-cols-[1fr_430px]">
          <GraphPanel
            nodes={activeNodes}
            edges={activeEdges}
            detected={audit?.corruption_detected ?? false}
          />
          <Panel
            title="CAG Audit Engine"
            subtitle="नियंत्रक एवं महालेखापरीक्षक"
            icon={<FileSearch className="h-5 w-5" />}
            accentColor="var(--pt-wheel-lt)"
          >
            <Slider
              label="Audit Depth"
              hindi="गहराई"
              value={auditLevel}
              min={1} max={8} step={1}
              onChange={setAuditLevel}
              accentColor="var(--pt-wheel-lt)"
              format={(v) => `${v}`}
            />
            <div className="mt-3 grid grid-cols-2 gap-3">
              <ActionBtn
                onClick={() => runAudit()}
                disabled={busyAction === "audit"}
                bg="var(--pt-wheel)" color="#fff"
                icon={<FileSearch className="h-4 w-4" />}
                label="RTI Query"
                busy={busyAction === "audit"}
                busyLabel="Chhaan Raha…"
              />
              <ActionBtn
                onClick={() => runAudit(Math.min(auditLevel + 1, 8))}
                disabled={busyAction === "audit"}
                bg="var(--pt-panel-hi)" color="var(--pt-white)"
                icon={<Bolt className="h-4 w-4" />}
                label="Upgrade"
                busy={busyAction === "audit"}
                busyLabel="…"
              />
            </div>
            <div
              className="mt-4 p-3"
              style={{ background: "var(--pt-ink)", border: `1px solid ${audit?.corruption_detected ? "var(--pt-red)" : "var(--pt-line)"}` }}
            >
              <div className="text-xs uppercase" style={{ color: "var(--pt-muted)" }}>CBI Nikarsh</div>
              <div
                className={`mt-1 font-bold text-sm ${audit?.corruption_detected ? "urgent" : ""}`}
                style={{ color: audit?.corruption_detected ? "var(--pt-red-lt)" : "var(--pt-white)" }}
              >
                {audit?.smoking_gun ?? audit?.next_upgrade_hint ?? "Saboot ka intezaar hai…"}
              </div>
            </div>
          </Panel>
        </section>

        {/* ── Election + Federal + News ─────────────────────────────────── */}
        <section className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr_0.8fr]">
          <ElectionPanel
            manifesto={manifesto}
            speech={speech}
            election={election}
            simulation={simulation}
            consecutiveTerms={consecutiveTerms}
            busy={busyAction === "election"}
            busyEmergency={busyAction === "emergency"}
            emergencyActive={state?.emergency_powers ?? false}
            role={role}
            onManifesto={setManifesto}
            onSpeech={setSpeech}
            onConsecutiveTerms={setConsecutiveTerms}
            onGrade={gradeElection}
            onDeclareEmergency={declareEmergency}
          />
          <FederalPanel
            busyGrant={busyAction === "grant"}
            busyTrade={busyAction === "trade"}
            grants={state?.federal_grants ?? []}
            buffs={state?.trade_buffs ?? []}
            onGrant={issueGrant}
            onTrade={resolveTradeDuel}
          />
          <NewsPanel headlines={state?.headlines ?? []} />
        </section>

        {/* ── Footer ─────────────────────────────────────────────────────── */}
        <footer
          className="mt-2 flex items-center justify-between pb-4 text-xs"
          style={{ color: "var(--pt-muted)", borderTop: "1px solid var(--pt-line)", paddingTop: "1rem" }}
        >
          <span>PrajaTantra · OpenFront Edition · भारत सिमुलेशन</span>
          <span style={{ color: "var(--pt-saffron)" }}>जय हिन्द 🇮🇳</span>
        </footer>
      </div>
    </main>
  );
}

// ─── NewsTicker — pure CSS scroll, stable key, no text-node thrashing ─────────
function NewsTicker({ headlines }: { headlines: string[] }) {
  const text = headlines.length > 0
    ? headlines.join("  ·  🔴 BREAKING:  ")
    : "Koi samachar nahi";
  // key={text} forces a full DOM remount when content changes,
  // so React never diffs text nodes that extensions may have split.
  return (
    <div
      className="mt-3 overflow-hidden py-1"
      style={{ background: "var(--pt-red)", fontSize: "0.7rem", letterSpacing: "0.05em", whiteSpace: "nowrap" }}
    >
      <div key={text} className="ticker-text font-bold" style={{ display: "inline-block" }}>
        {"🔴 BREAKING:  " + text}
      </div>
    </div>
  );
}

// ─── SeatBadge — shows the server-assigned seat (locked, not togglable),
// plus live connection + opponent-presence status. Replaces the old
// client-side RoleSwitch: in multiplayer, role is never something a
// player gets to just click into. ───────────────────────────────────────
function SeatBadge({
  role, match, connected, opponentOnline, onLeaveMatch,
}: {
  role: PlayerRole;
  match: MatchInfo | null;
  connected: boolean;
  opponentOnline: boolean;
  onLeaveMatch: () => void;
}) {
  const color = role === "Incumbent" ? "var(--pt-saffron)" : "var(--pt-red)";
  const hindi = role === "Incumbent" ? "मुख्यमंत्री" : "विपक्ष नेता";
  const opponentSeat = role === "Incumbent" ? match?.opposition : match?.incumbent;

  return (
    <div
      className="flex flex-col justify-center gap-1 px-3 py-2"
      style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-black uppercase" style={{ color }}>
            {role === "Incumbent" ? "Ruling Party (CM)" : "Opposition"}
          </div>
          <div className="text-[10px] opacity-70" style={{ color }}>{hindi}</div>
        </div>
        <span
          className="h-2 w-2 rounded-full"
          style={{ background: connected ? "var(--pt-green-lt)" : "var(--pt-red)" }}
          title={connected ? "Live" : "Reconnecting…"}
        />
      </div>
      <div className="flex items-center justify-between text-[9px]" style={{ color: "var(--pt-muted)" }}>
        <span className="flex items-center gap-1">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: opponentOnline ? "var(--pt-green-lt)" : "var(--pt-muted)" }}
          />
          {opponentSeat ? `${opponentSeat.username} ${opponentOnline ? "online" : "away"}` : "Waiting for opponent…"}
        </span>
        <button type="button" onClick={onLeaveMatch} className="underline" style={{ color: "var(--pt-muted)" }}>
          Leave
        </button>
      </div>
    </div>
  );
}

// ─── FlashPanel — live alert ticker ────────────────────────────────────────
function FlashPanel({ flash }: { flash: string }) {
  return (
    <div
      className="flex flex-col justify-center px-4 py-3"
      style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}
    >
      <div className="text-xs uppercase" style={{ color: "var(--pt-muted)" }}>
        🔴 LIVE — Akhbaar
      </div>
      <div className="mt-1 text-sm font-semibold" style={{ color: "var(--pt-saffron)" }}>
        {flash}
      </div>
    </div>
  );
}

// ─── Metric card ─────────────────────────────────────────────────────────
function Metric({
  label, hindi, value, tone,
}: { label: string; hindi: string; value: string; tone: string }) {
  return (
    <div
      className="px-4 py-3"
      style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}
    >
      <div className="text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>{label}</div>
      <div className="text-[10px]" style={{ color: "var(--pt-muted)", opacity: 0.7 }}>{hindi}</div>
      <div className="mt-1 text-2xl font-black" style={{ color: tone }}>{value}</div>
    </div>
  );
}

// ─── Generic Panel wrapper ────────────────────────────────────────────────
function Panel({
  title, subtitle, icon, accentColor, children, locked = false, lockedLabel, fill = false,
}: {
  title: string;
  subtitle?: string;
  icon: ReactNode;
  accentColor?: string;
  children: ReactNode;
  locked?: boolean;
  lockedLabel?: string;
  fill?: boolean;
}) {
  return (
    <section
      className={`relative p-4 ${fill ? "h-full" : ""}`}
      style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}
    >
      <div
        className="mb-4 flex items-center justify-between pb-3"
        style={{ borderBottom: "1px solid var(--pt-line)" }}
      >
        <div className="flex items-center gap-2">
          <span style={{ color: locked ? "var(--pt-muted)" : (accentColor ?? "var(--pt-saffron)") }}>
            {icon}
          </span>
          <div>
            <div className="font-black text-sm">{title}</div>
            {subtitle && (
              <div className="text-[10px]" style={{ color: "var(--pt-muted)" }}>{subtitle}</div>
            )}
          </div>
        </div>
        {locked && lockedLabel && (
          <span
            className="px-2 py-1 text-xs font-bold uppercase"
            style={{ border: "1px solid var(--pt-red)", color: "var(--pt-red-lt)" }}
          >
            {lockedLabel}
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

// ─── Segmented control ────────────────────────────────────────────────────
function Segmented({
  value, options, onChange,
}: { value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div
      className="grid grid-cols-3 p-1"
      style={{ border: "1px solid var(--pt-line)", background: "var(--pt-ink)" }}
    >
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onChange(opt)}
          className="flex h-10 flex-col items-center justify-center gap-0.5 text-[10px] font-black uppercase transition-all"
          style={
            value === opt
              ? { background: "var(--pt-saffron)", color: "#fff" }
              : { color: "var(--pt-muted)" }
          }
        >
          {blockIcons[opt as PortfolioType]}
          <span>{blockLabels[opt as PortfolioType].hindi}</span>
        </button>
      ))}
    </div>
  );
}

// ─── Slider ───────────────────────────────────────────────────────────────
function Slider({
  label, hindi, value, min, max, step, suffix = "", onChange, accentColor, format,
}: {
  label: string;
  hindi?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix?: string;
  onChange: (v: number) => void;
  accentColor?: string;
  format?: (v: number) => string;
}) {
  const display = format ? format(value) : suffix ? `${value}${suffix}` : formatCrore(value);
  return (
    <label className="grid gap-1">
      <span className="flex items-center justify-between text-sm">
        <span>
          <span className="text-xs" style={{ color: "var(--pt-muted)" }}>{label}</span>
          {hindi && <span className="ml-1 text-[10px]" style={{ color: "var(--pt-muted)", opacity: 0.6 }}>{hindi}</span>}
        </span>
        <span className="font-black text-xs" style={{ color: accentColor ?? "var(--pt-saffron)" }}>
          {display}
        </span>
      </span>
      <input
        type="range"
        min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-2"
        style={{ accentColor: accentColor ?? "var(--pt-saffron)" }}
      />
    </label>
  );
}

// ─── ImpactPreview ────────────────────────────────────────────────────────
function ImpactPreview({ blockType, budget, siphon }: { blockType: PortfolioType; budget: number; siphon: number }) {
  const values =
    blockType === "Industrial"
      ? [["Aay (₹)", budget * 0.2], ["Pradooshan", 10 + siphon / 10], ["Asantosh", 7 + siphon / 10]]
      : blockType === "Social"
      ? [["Vishwas", 12 - siphon / 10], ["Swasthya", 9], ["Rakhrakha (₹)", budget * 0.08]]
      : [["Gaurav", 14], ["Anusandhan", 8], ["Rakhrakha (₹)", budget * 0.03]];
  return (
    <div className="mt-4 grid grid-cols-3 gap-2">
      {values.map(([lbl, val]) => (
        <div
          key={lbl as string}
          className="p-3"
          style={{ border: "1px solid var(--pt-line)", background: "var(--pt-ink)" }}
        >
          <div className="text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>{lbl as string}</div>
          <div className="mt-1 text-base font-black">
            {typeof val === "number" && val > 1000 ? formatCrore(val) : Math.round(Number(val))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── BlockTile (constituency card) ────────────────────────────────────────
function BlockTile({
  block, selected, onSelect,
}: { block: InfrastructureBlock; selected: boolean; onSelect: () => void }) {
  const accent =
    block.portfolio_type === "Industrial"
      ? "var(--pt-gold)"
      : block.portfolio_type === "Social"
      ? "var(--pt-green)"
      : "var(--pt-wheel)";
  return (
    <button
      type="button"
      onClick={onSelect}
      className="min-h-[156px] p-4 text-left transition-all"
      style={{
        background: "var(--pt-ink)",
        border: `1px solid ${selected ? accent : "var(--pt-line)"}`,
        boxShadow: selected ? `0 0 0 2px ${accent}40` : "none",
      }}
    >
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1 text-[10px] font-bold uppercase" style={{ color: "var(--pt-muted)" }}>
          {blockIcons[block.portfolio_type]}
          {blockLabels[block.portfolio_type].hindi}
        </span>
        <span className="text-[10px]" style={{ color: accent }}>L{block.level}</span>
      </div>
      <div className="mt-2 text-base font-black leading-tight">{block.name}</div>
      <div className="mt-3 grid grid-cols-2 gap-1 text-xs" style={{ color: "var(--pt-muted)" }}>
        <span>₹ {formatCrore(block.gold_per_tick)}</span>
        <span>Maint {formatCrore(block.maintenance)}</span>
        <span style={{ color: block.trust_delta >= 0 ? "var(--pt-green-lt)" : "var(--pt-red-lt)" }}>
          Vishwas {signed(block.trust_delta)}
        </span>
        <span style={{ color: block.unrest_delta > 0 ? "var(--pt-red-lt)" : "var(--pt-green-lt)" }}>
          Asant {signed(block.unrest_delta)}
        </span>
      </div>
    </button>
  );
}

// ─── Corruption Graph ─────────────────────────────────────────────────────
function GraphPanel({
  nodes, edges, detected,
}: { nodes: GraphNode[]; edges: GraphEdge[]; detected: boolean }) {
  return (
    <Panel
      title="ED / CBI Bhrashtachar Graph"
      subtitle="भ्रष्टाचार नेटवर्क"
      icon={<Gavel className="h-5 w-5" />}
      accentColor={detected ? "var(--pt-red)" : "var(--pt-wheel-lt)"}
      fill
    >
      <div
        className="chakra-grid min-h-[360px] p-4"
        style={{ border: "1px solid var(--pt-line)", background: "var(--pt-ink)" }}
      >
        <div className="flex min-h-[260px] flex-wrap content-center items-center gap-3">
          {nodes.length === 0 ? (
            <div className="mx-auto text-center text-sm" style={{ color: "var(--pt-muted)" }}>
              <Scale className="mx-auto mb-2 h-8 w-8 opacity-30" />
              Koi graph path load nahi hua
            </div>
          ) : (
            nodes.map((node, idx) => (
              <div key={node.id} className="flex items-center gap-3">
                <GraphNodeBadge node={node} detected={detected && node.label === "Player"} />
                {idx < nodes.length - 1 && (
                  <div className="h-px w-10" style={{ background: "var(--pt-saffron)" }} />
                )}
              </div>
            ))
          )}
        </div>
        <div className="ledger-scroll mt-3 grid max-h-28 gap-2 overflow-auto text-xs" style={{ color: "var(--pt-muted)" }}>
          {edges.map((edge) => (
            <div
              key={`${edge.source}-${edge.target}-${edge.type}`}
              className="px-2 py-1"
              style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}
            >
              {edge.type} / {Object.entries(edge.properties)[0]?.join(": ") ?? "darj"}
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function GraphNodeBadge({ node, detected }: { node: GraphNode; detected: boolean }) {
  const tone =
    node.label === "Player"
      ? { border: "var(--pt-red)", color: "var(--pt-red-lt)" }
      : node.label === "Account"
      ? { border: "var(--pt-gold)", color: "var(--pt-gold)" }
      : node.label === "Vendor"
      ? { border: "var(--pt-saffron)", color: "var(--pt-saffron)" }
      : { border: "var(--pt-line)", color: "var(--pt-white)" };
  return (
    <div
      className={`min-w-[130px] px-3 py-3 text-center ${detected ? "scam-ring" : ""}`}
      style={{
        border: `1px solid ${tone.border}`,
        background: "var(--pt-panel)",
        color: tone.color,
      }}
    >
      <div className="text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>{node.label}</div>
      <div className="mt-1 text-sm font-black">{node.name}</div>
    </div>
  );
}

// ─── Election Panel — चुनाव अभियान (with 24-Round Simulation + Seat Map) ──
function ElectionPanel({
  manifesto, speech, election, simulation,
  consecutiveTerms,
  busy, busyEmergency, emergencyActive, role,
  onManifesto, onSpeech,
  onConsecutiveTerms,
  onGrade,
  onDeclareEmergency,
}: {
  manifesto: string;
  speech: string;
  election: ElectionResponse | null;
  simulation: TenRoundSimulationResponse | null;
  consecutiveTerms: number;
  busy: boolean;
  busyEmergency: boolean;
  emergencyActive: boolean;
  role: PlayerRole;
  onManifesto: (v: string) => void;
  onSpeech: (v: string) => void;
  onConsecutiveTerms: (v: number) => void;
  onGrade: () => void;
  onDeclareEmergency: () => void;
}) {
  // Read the derived scores echoed back in the simulation result
  const incScore = simulation
    ? Math.round((simulation.final_incumbent_votes / (simulation.final_incumbent_votes + simulation.final_opposition_votes)) * 100)
    : null;
  const oppScore = incScore !== null ? 100 - incScore : null;

  return (
    <Panel
      title="Chunaav Abhiyaan"
      subtitle="चुनाव अभियान"
      icon={<Vote className="h-5 w-5" />}
      accentColor="var(--pt-green-lt)"
    >
      {/* ── Election-day schedule note ─────────────────────────── */}
      <div className="mb-3 flex items-center gap-2 text-[10px]" style={{ color: "var(--pt-muted)" }}>
        <Radio className="h-3 w-3 opacity-60" />
        Chunaav har {simulation?.election_cycle_days ?? 3} din par hota hai · Matganak{" "}
        {simulation?.counting_duration_hours ?? 2} ghante, {simulation?.total_rounds ?? 24} rounds mein.
      </div>

      {/* ── Manifesto & Speech ─────────────────────────────────── */}
      <div className="grid gap-3">
        <div>
          <div className="mb-1 text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>
            घोषणापत्र — Ghoshanapatra (Manifesto) · AI-judged via HuggingFace
          </div>
          <textarea
            value={manifesto}
            onChange={(e) => onManifesto(e.target.value)}
            className="h-20 w-full resize-none p-3 text-sm outline-none"
            style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)", color: "var(--pt-white)" }}
            
            
          />
        </div>
        <div>
          <div className="mb-1 text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>
            चुनाव भाषण — Chunaav Bhashan (Campaign Speech)
          </div>
          <textarea
            value={speech}
            onChange={(e) => onSpeech(e.target.value)}
            className="h-20 w-full resize-none p-3 text-sm outline-none"
            style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)", color: "var(--pt-white)" }}
            
            
          />
        </div>
      </div>

      {/* ── Only user-controlled input: consecutive terms ─────── */}
      <div
        className="mt-3 p-3"
        style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)" }}
      >
        <Slider
          label="Consecutive Terms in Power"
          hindi="लगातार कार्यकाल (मतदाता थकान)"
          value={consecutiveTerms}
          min={0} max={5} step={1}
          onChange={onConsecutiveTerms}
          accentColor="var(--pt-wheel-lt)"
          format={(v) => `${v} term${v !== 1 ? "s" : ""}`}
        />
        <div className="mt-2 text-[10px]" style={{ color: "var(--pt-muted)" }}>
          ⚠️ Satta paksh ke baaki saare scores live city data, manifesto AI-judging, aur anti-incumbency se derive hote hain — aap inhe badal nahi sakte.
        </div>
      </div>

      {/* ── Auto-derived strength bars — read-only ─────────────── */}
      {simulation && incScore !== null && oppScore !== null && (
        <div
          className="mt-3 p-3"
          style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)" }}
        >
          <div className="mb-2 text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>
            Derived Jansharti (Auto-calculated from city state)
          </div>
          <StrengthBar label="Satta Paksh" value={incScore} color="var(--pt-saffron)" />
          <StrengthBar label="Vipaksh" value={oppScore} color="var(--pt-green)" />
          <div className="mt-1 text-[10px]" style={{ color: "var(--pt-muted)" }}>
            Wave: <span style={{ color: "var(--pt-gold)" }}>{simulation.wave_label}</span>
            &nbsp;·&nbsp; I<sub>f</sub>: {simulation.incumbency_factor > 0 ? "+" : ""}{simulation.incumbency_factor}
            {election && (
              <>
                &nbsp;·&nbsp; Manifesto AI: <span style={{ color: "var(--pt-gold)" }}>
                  {election.breakdown["manifesto_ai_score"] ?? "—"}/100
                </span> ({String(election.breakdown["manifesto_ai_source"] ?? "n/a")})
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Run button ─────────────────────────────────────────── */}
      <button
        type="button"
        onClick={onGrade}
        disabled={busy}
        className="mt-3 flex h-11 w-full items-center justify-center gap-2 font-black disabled:opacity-50"
        style={{ background: "var(--pt-green)", border: "1px solid var(--pt-green)", color: "#fff" }}
      >
        <UsersRound className="h-5 w-5" />
        {busy ? "Matganak Ho Raha Hai…" : "Chunaav Simulate Karein 🗳️"}
      </button>

      {/* ── 24-Round SVG Chart ─────────────────────────────────── */}
      <TenRoundChart simulation={simulation} />

      {/* ── Seat map (hemicycle chart) ──────────────────────────── */}
      {simulation && (simulation.seats?.length ?? 0) > 0 && (
        <SeatMap
          key={`${simulation.total_seats}-${simulation.incumbent_seats}-${simulation.opposition_seats}-${simulation.margin}`}
          seats={simulation.seats}
          totalSeats={simulation.total_seats ?? 101}
          incumbentName={simulation.incumbent_name ?? "Sattadheen Dal"}
          oppositionName={simulation.opposition_name ?? "Vipaksh Dal"}
        />
      )}

      {/* ── Emergency / supermajority powers ────────────────────── */}
      {simulation && (simulation.emergency_eligible || emergencyActive) && (
        <div
          className="mt-3 p-3"
          style={{ background: "rgba(192,41,42,0.08)", border: "1px solid var(--pt-red)" }}
        >
          <div className="flex items-center gap-2 text-xs font-black" style={{ color: "var(--pt-red-lt)" }}>
            <Siren className="h-4 w-4" />
            {emergencyActive ? "Aapatkaal Laagu Hai — Emergency in Effect" : "Supermajority Cleared"}
          </div>
          <div className="mt-1 text-[10px]" style={{ color: "var(--pt-muted)" }}>
            {emergencyActive
              ? "Industrial construction bypasses Residential zoning citywide, jaise ek dictatorship city planning ko override kar rahi ho."
              : simulation.emergency_message ?? `Incumbent crossed ${simulation.emergency_threshold_pct ?? 80}% of seats.`}
          </div>
          {!emergencyActive && (
            <button
              type="button"
              onClick={onDeclareEmergency}
              disabled={busyEmergency || role !== "Incumbent"}
              className="mt-2 flex h-9 w-full items-center justify-center gap-2 text-xs font-black disabled:opacity-50"
              style={{ background: "var(--pt-red)", border: "1px solid var(--pt-red)", color: "#fff" }}
            >
              <ShieldAlert className="h-4 w-4" />
              {busyEmergency
                ? "Ghoshit Ho Raha Hai…"
                : role === "Incumbent"
                ? "Aapatkaal Ghoshit Karein — Declare Emergency"
                : "Sirf Incumbent Emergency Ghoshit Kar Sakta Hai"}
            </button>
          )}
        </div>
      )}

      {/* ── Score cards ───────────────────────────────────────── */}
      <div className="mt-3 grid grid-cols-4 gap-2">
        <LedgerStat label="Vyavharik"  value={`${election?.practicality_score ?? 0}`}       accent="var(--pt-saffron)" />
        <LedgerStat label="Bhashan"    value={`${election?.rhetoric_score ?? 0}`}            accent="var(--pt-green-lt)" />
        <LedgerStat label="Shehar"     value={`${election?.city_performance_score ?? 0}`}    accent="var(--pt-wheel-lt)" />
        <LedgerStat label="Vishwas"    value={`${election?.trust_score ?? 0}`}               accent="var(--pt-gold)" />
      </div>
    </Panel>
  );
}

// ─── StrengthBar — read-only vote-strength bar ───────────────────────────────
function StrengthBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="mb-2">
      <div className="mb-1 flex justify-between text-[10px]">
        <span style={{ color: "var(--pt-muted)" }}>{label}</span>
        <span className="font-black" style={{ color }}>{value}%</span>
      </div>
      <div className="h-2 w-full rounded-none" style={{ background: "var(--pt-panel-hi)" }}>
        <div
          className="h-2 transition-all duration-700"
          style={{ width: `${value}%`, background: color }}
        />
      </div>
    </div>
  );
}

// ─── TenRoundChart — SVG line chart matching the design in the spec ─────────
function TenRoundChart({ simulation }: { simulation: TenRoundSimulationResponse | null }) {
  if (!simulation) {
    return (
      <div
        className="mt-3 flex h-44 items-center justify-center text-xs"
        style={{ border: "1px solid var(--pt-line)", background: "var(--pt-ink)", color: "var(--pt-muted)" }}
      >
        <Vote className="mr-2 h-4 w-4 opacity-40" />
        Simulate karein — chart yahan dikhega
      </div>
    );
  }

  const rounds = simulation.rounds;
  const total  = simulation.final_incumbent_votes + simulation.final_opposition_votes;
  const victory50 = total / 2;

  // Chart dimensions
  const W = 560;
  const H = 160;
  const PAD_L = 44;
  const PAD_R = 12;
  const PAD_T = 12;
  const PAD_B = 28;
  const chartW = W - PAD_L - PAD_R;
  const chartH = H - PAD_T - PAD_B;

  const maxVotes = Math.max(
    ...rounds.map((r) => Math.max(r.running_incumbent_total, r.running_opposition_total)),
    victory50,
  );

  const totalRounds = simulation.total_rounds ?? 24;

  function xOf(round: number) {
    return PAD_L + (round / totalRounds) * chartW;
  }
  function yOf(votes: number) {
    return PAD_T + chartH - (votes / maxVotes) * chartH;
  }

  // Build polyline points
  const incPoints = [
    `${PAD_L},${PAD_T + chartH}`,
    ...rounds.map((r) => `${xOf(r.round)},${yOf(r.running_incumbent_total)}`),
  ].join(" ");
  const oppPoints = [
    `${PAD_L},${PAD_T + chartH}`,
    ...rounds.map((r) => `${xOf(r.round)},${yOf(r.running_opposition_total)}`),
  ].join(" ");

  // Y-axis tick labels (5 evenly spaced)
  const yTicks = [0, 0.25, 0.5, 0.75, 1.0].map((t) => ({
    votes: Math.round(maxVotes * t),
    y:     yOf(maxVotes * t),
  }));

  const incWins = simulation.final_incumbent_votes >= simulation.final_opposition_votes;

  return (
    <div className="mt-3" style={{ border: "1px solid var(--pt-line)", background: "var(--pt-ink)" }}>
      {/* Legend */}
      <div className="flex items-center gap-4 px-3 pt-2 text-[10px]">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-6 rounded" style={{ background: "var(--pt-saffron)" }} />
          <span style={{ color: "var(--pt-muted)" }}>{simulation.incumbent_name ?? "Sattadheen Dal"} (सत्ता पक्ष)</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-6 rounded" style={{ background: "var(--pt-green)" }} />
          <span style={{ color: "var(--pt-muted)" }}>{simulation.opposition_name ?? "Vipaksh Dal"} (विपक्ष)</span>
        </span>
      </div>

      {/* SVG chart */}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        style={{ display: "block" }}
        aria-label="24-Round election counting chart"
      >
        {/* Horizontal grid lines */}
        {yTicks.map(({ y }) => (
          <line
            key={y}
            x1={PAD_L} y1={y} x2={W - PAD_R} y2={y}
            stroke="rgba(255,255,255,0.06)" strokeWidth="1"
          />
        ))}

        {/* Y-axis labels */}
        {yTicks.map(({ votes, y }) => (
          <text
            key={votes}
            x={PAD_L - 4} y={y + 3}
            textAnchor="end"
            fontSize="8"
            fill="rgba(255,255,255,0.3)"
          >
            {votes >= 1000 ? `${(votes / 1000).toFixed(0)}K` : votes}
          </text>
        ))}

        {/* 50% victory dashed line */}
        <line
          x1={PAD_L} y1={yOf(victory50)}
          x2={W - PAD_R} y2={yOf(victory50)}
          stroke="rgba(255,255,255,0.25)"
          strokeWidth="1"
          strokeDasharray="4 3"
        />
        <text
          x={PAD_L + 4} y={yOf(victory50) - 3}
          fontSize="8" fill="rgba(255,255,255,0.35)"
        >
          50% Vijay Rekha
        </text>

        {/* Opposition line */}
        <polyline
          points={oppPoints}
          fill="none"
          stroke="var(--pt-green)"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        {rounds.map((r) => (
          <circle
            key={`opp-${r.round}`}
            cx={xOf(r.round)} cy={yOf(r.running_opposition_total)}
            r="3" fill="var(--pt-green)"
          />
        ))}

        {/* Incumbent line (drawn on top) */}
        <polyline
          points={incPoints}
          fill="none"
          stroke="var(--pt-saffron)"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        {rounds.map((r) => (
          <circle
            key={`inc-${r.round}`}
            cx={xOf(r.round)} cy={yOf(r.running_incumbent_total)}
            r="3" fill="var(--pt-saffron)"
          />
        ))}

        {/* X-axis round labels — every 3rd round to avoid crowding at 24 rounds */}
        {rounds.filter((r) => r.round % 3 === 0 || r.round === rounds.length).map((r) => (
          <text
            key={r.round}
            x={xOf(r.round)} y={H - 8}
            textAnchor="middle"
            fontSize="8"
            fill="rgba(255,255,255,0.3)"
          >
            {r.round}
          </text>
        ))}
        <text x={PAD_L} y={H - 8} textAnchor="middle" fontSize="8" fill="rgba(255,255,255,0.2)">0</text>
      </svg>

      {/* Result bar */}
      <div
        className="flex items-center justify-between px-3 pb-2 text-xs font-black"
        style={{ borderTop: "1px solid var(--pt-line)" }}
      >
        <span style={{ color: "var(--pt-saffron)" }}>
          Satta: {simulation.final_incumbent_votes.toLocaleString("en-IN")}
        </span>
        <span
          className="px-3 py-1 text-[10px]"
          style={{
            background: incWins ? "var(--pt-saffron)" : "var(--pt-green)",
            color: "#fff",
          }}
        >
          🏆 {simulation.winner}
        </span>
        <span style={{ color: "var(--pt-green-lt)" }}>
          Vipaksh: {simulation.final_opposition_votes.toLocaleString("en-IN")}
        </span>
      </div>
    </div>
  );
}

// ─── Federal Panel — केंद्र सरकार ────────────────────────────────────────
function FederalPanel({
  busyGrant, busyTrade, grants, buffs, onGrant, onTrade,
}: {
  busyGrant: boolean;
  busyTrade: boolean;
  grants: string[];
  buffs: string[];
  onGrant: () => void;
  onTrade: () => void;
}) {
  return (
    <Panel
      title="Kendra Sarkar"
      subtitle="केंद्र सरकार"
      icon={<Globe2 className="h-5 w-5" />}
      accentColor="var(--pt-wheel-lt)"
    >
      <div className="grid grid-cols-2 gap-3">
        <ActionBtn
          onClick={onGrant}
          disabled={busyGrant}
          bg="var(--pt-wheel)" color="#fff"
          icon={<Banknote className="h-4 w-4" />}
          label="Anudan (Grant)"
          busy={busyGrant}
          busyLabel="Bhej Raha…"
        />
        <ActionBtn
          onClick={onTrade}
          disabled={busyTrade}
          bg="var(--pt-gold)" color="#0C0F14"
          icon={<Globe2 className="h-4 w-4" />}
          label="Vyaapaar Duel"
          busy={busyTrade}
          busyLabel="Hisaab…"
        />
      </div>
      <EventList items={[...grants, ...buffs]} emptyMsg="Koi kendra dispatch nahi." />
    </Panel>
  );
}

// ─── News Panel — समाचार पत्र ──────────────────────────────────────────
function NewsPanel({ headlines }: { headlines: string[] }) {
  return (
    <Panel
      title="Chauthaa Khamba"
      subtitle="चौथा खम्भा (Press)"
      icon={<Newspaper className="h-5 w-5" />}
      accentColor="var(--pt-red-lt)"
    >
      <EventList items={headlines} emptyMsg="Koi samachaar nahi." />
    </Panel>
  );
}

// ─── EventList ────────────────────────────────────────────────────────────
function EventList({ items, emptyMsg = "No dispatches." }: { items: string[]; emptyMsg?: string }) {
  return (
    <div className="ledger-scroll mt-4 grid max-h-72 gap-3 overflow-auto">
      {items.length === 0 ? (
        <div
          className="p-3 text-sm"
          style={{ border: "1px solid var(--pt-line)", background: "var(--pt-ink)", color: "var(--pt-muted)" }}
        >
          {emptyMsg}
        </div>
      ) : (
        items.map((item) => (
          <div
            key={item}
            className="px-4 py-3 text-sm leading-6"
            style={{ borderLeft: "4px solid var(--pt-saffron)", background: "var(--pt-ink)" }}
          >
            {item}
          </div>
        ))
      )}
    </div>
  );
}

// ─── LedgerStat ───────────────────────────────────────────────────────────
function LedgerStat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div
      className="p-3"
      style={{ border: "1px solid var(--pt-line)", background: "var(--pt-ink)" }}
    >
      <div className="text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>{label}</div>
      <div className="mt-1 text-lg font-black" style={{ color: accent ?? "var(--pt-white)" }}>
        {value}
      </div>
    </div>
  );
}

// ─── ActionBtn ────────────────────────────────────────────────────────────
function ActionBtn({
  onClick, disabled, bg, color, icon, label, busy, busyLabel,
}: {
  onClick: () => void;
  disabled: boolean;
  bg: string;
  color: string;
  icon: ReactNode;
  label: string;
  busy: boolean;
  busyLabel: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex h-11 items-center justify-center gap-2 text-sm font-black disabled:cursor-not-allowed disabled:opacity-45"
      style={{ background: bg, color, border: `1px solid ${bg}` }}
    >
      {icon}
      {busy ? busyLabel : label}
    </button>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────
function formatCrore(value: number) {
  const abs = Math.abs(value);
  if (abs >= 10_000_000) return `₹${(value / 10_000_000).toFixed(2)} Cr`;
  if (abs >= 100_000)    return `₹${(value / 100_000).toFixed(1)} L`;
  if (abs >= 1_000)      return `₹${Math.round(value / 1_000)}K`;
  return `₹${Math.round(value)}`;
}

function signed(value: number) {
  return value > 0 ? `+${value}` : `${value}`;
}

function messageFromError(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

// ─── Home — top-level auth gate ────────────────────────────────────────────
// Wraps the Dashboard behind login/register. Session (token + player) is
// persisted to localStorage so a page refresh doesn't log the player out.
// Match membership (match_id) is persisted separately so a refresh mid-game
// reconnects to the same match instead of dropping back to the lobby.
const SESSION_KEY = "prajatantra.session.v1";
const MATCH_KEY = "prajatantra.match_id.v1";

export default function Home() {
  const [session, setSession] = useState<AuthResponse | null>(null);
  const [bootChecked, setBootChecked] = useState(false);
  const [matchId, setMatchId] = useState<string | null>(null);

  // Restore session on mount
  useEffect(() => {
    let savedToken: string | null = null;
    try {
      const raw = window.localStorage.getItem(SESSION_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as AuthResponse;
        savedToken = parsed.token;
        setSession(parsed);
        // Validate token is still accepted by the backend; if not, clear it.
        api.me(parsed.token).catch(() => {
          window.localStorage.removeItem(SESSION_KEY);
          setSession(null);
        });
      }
    } catch {
      window.localStorage.removeItem(SESSION_KEY);
    }

    // Matches live in server memory only — a backend restart/redeploy wipes
    // them. If the saved match_id no longer exists server-side, drop back
    // to the lobby instead of endlessly retrying a WebSocket that will
    // always be rejected pre-handshake (surfaces as a confusing 403).
    const savedMatch = window.localStorage.getItem(MATCH_KEY);
    if (savedMatch && savedToken) {
      matchApi.getState(savedMatch, savedToken)
        .then(() => setMatchId(savedMatch))
        .catch(() => window.localStorage.removeItem(MATCH_KEY));
    } else if (savedMatch) {
      // No session to validate against (yet) — keep it optimistically;
      // it'll be re-checked once login resolves on a future mount.
      setMatchId(savedMatch);
    }

    setBootChecked(true);
  }, []);

  function handleAuth(response: AuthResponse) {
    setSession(response);
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(response));
  }

  function handleLogout() {
    setSession(null);
    setMatchId(null);
    window.localStorage.removeItem(SESSION_KEY);
    window.localStorage.removeItem(MATCH_KEY);
  }

  function handleCityRenamed(newName: string) {
    if (!session) return;
    const updated: AuthResponse = { ...session, player: { ...session.player, city_name: newName } };
    setSession(updated);
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(updated));
  }

  function handleMatched(match: MatchInfo) {
    setMatchId(match.match_id);
    window.localStorage.setItem(MATCH_KEY, match.match_id);
  }

  function handleLeaveMatch() {
    setMatchId(null);
    window.localStorage.removeItem(MATCH_KEY);
  }

  if (!bootChecked) {
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        style={{ background: "var(--pt-ink)", color: "var(--pt-saffron)" }}
      >
        🇮🇳 लोड हो रहा है…
      </div>
    );
  }

  if (!session) {
    return <AuthGate onAuth={handleAuth} />;
  }

  if (!matchId) {
    return (
      <main className="min-h-screen" style={{ background: "var(--pt-ink)", color: "var(--pt-white)" }}>
        <div className="tricolour-bar" />
        <MatchLobby token={session.token} onMatched={handleMatched} />
      </main>
    );
  }

  return (
    <Dashboard
      player={session.player}
      token={session.token}
      matchId={matchId}
      onCityRenamed={handleCityRenamed}
      onLogout={handleLogout}
      onLeaveMatch={handleLeaveMatch}
    />
  );
}
