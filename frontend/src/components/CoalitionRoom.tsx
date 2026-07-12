"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Banknote,
  Crown,
  Gavel,
  HandCoins,
  Handshake,
  Landmark,
  LogOut,
  Radio,
  ShieldAlert,
  Swords,
  Vote,
} from "lucide-react";

import { CoalitionMatchInfo, CoalitionSeat, Ministry, coalitionApi } from "@/lib/coalitionApi";
import { useCoalitionSocket } from "@/lib/useCoalitionSocket";
import ElectionRoundsAnnouncer from "@/components/ElectionRoundsAnnouncer";

const PARTY_COLORS = ["#FF9933", "#138808", "#0F52BA", "#B8860B", "#8B0000"];

export default function CoalitionRoom({
  matchId, token, myPlayerId, onLeave,
}: {
  matchId: string;
  token: string;
  myPlayerId: string;
  onLeave: () => void;
}) {
  const { match: socketMatch, connected } = useCoalitionSocket(matchId, token);
  const [match, setMatch] = useState<CoalitionMatchInfo | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now() / 1000);

  useEffect(() => { if (socketMatch) setMatch(socketMatch); }, [socketMatch]);
  useEffect(() => {
    coalitionApi.getState(matchId, token).then((r) => setMatch(r.match)).catch(() => {});
  }, [matchId, token]);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(id);
  }, []);

  const seatById = useMemo(() => {
    const map: Record<string, CoalitionSeat> = {};
    (match?.seats ?? []).forEach((s) => { map[s.player_id] = s; });
    return map;
  }, [match]);

  const me = match?.seats.find((s) => s.player_id === myPlayerId) ?? null;
  const isCM = match?.cm_player_id === myPlayerId;
  const inGovernment = me?.in_government ?? false;

  async function run<T>(key: string, fn: () => Promise<T>) {
    setBusy(key);
    setError(null);
    try {
      const result: any = await fn();
      if (result?.match) setMatch(result.match);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kuch gadbad ho gayi.");
    } finally {
      setBusy(null);
    }
  }

  if (!match) {
    return (
      <div className="mx-auto mt-16 max-w-md p-6 text-center text-sm" style={{ color: "var(--pt-muted)" }}>
        Coalition room load ho raha hai…
      </div>
    );
  }

  return (
    <main className="min-h-screen" style={{ color: "var(--pt-white)" }}>
      <div className="tricolour-bar" />
      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-4 px-4 pb-10 pt-8">
        {/* ── Header ─────────────────────────────────────────────── */}
        <header className="flex flex-wrap items-center justify-between gap-3 pb-3" style={{ borderBottom: "1px solid var(--pt-line)" }}>
          <div className="flex items-center gap-2 text-xs uppercase" style={{ color: "var(--pt-saffron)" }}>
            <Landmark className="h-4 w-4" />
            The Coalition Era — 5-Player Assembly
            <span className="px-2 py-1 text-[10px]" style={{ border: "1px solid var(--pt-line)", color: "var(--pt-muted)" }}>
              Code {match.join_code}
            </span>
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: connected ? "var(--pt-green-lt)" : "var(--pt-red)" }}
              title={connected ? "Live" : "Reconnecting…"}
            />
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={match.status} />
            <span className="text-xs" style={{ color: "var(--pt-gold)" }}>
              <Banknote className="mr-1 inline h-3 w-3" />₹{match.treasury.toLocaleString("en-IN")}
            </span>
            <button type="button" onClick={onLeave} className="flex items-center gap-1 px-2 py-1 text-[11px]" style={{ border: "1px solid var(--pt-line)", color: "var(--pt-muted)" }}>
              <LogOut className="h-3 w-3" /> Leave
            </button>
          </div>
        </header>

        {error && (
          <div className="px-3 py-2 text-[11px]" style={{ border: "1px solid var(--pt-red)", color: "var(--pt-red-lt)" }}>
            {error}
          </div>
        )}

        {/* ── Assembly seat bar (101 seats, magic number 51) ──────── */}
        <SeatDistributionBar seats={match.seats} magicNumber={51} totalSeats={101} />

        {/* ── Negotiation ───────────────────────────────────────── */}
        {match.status === "negotiating" && (
          <NegotiationPanel
            match={match}
            myPlayerId={myPlayerId}
            busy={busy}
            onPropose={(partnerIds) => run("propose", () => coalitionApi.propose(matchId, token, partnerIds))}
            onRespond={(proposalId, accept) => run("respond", () => coalitionApi.respond(matchId, token, proposalId, accept))}
            now={now}
          />
        )}

        {/* ── Governing / Floor Test ───────────────────────────────── */}
        {(match.status === "governing" || match.status === "floor_test") && (
          <>
            <GovernmentPanel match={match} myPlayerId={myPlayerId} seatById={seatById} />

            <div className="grid gap-4 lg:grid-cols-2">
              {isCM && (
                <MinistryPanel
                  match={match}
                  busy={busy}
                  onAllocate={(ministerId, ministry) =>
                    run("ministry", () => coalitionApi.allocateMinistry(matchId, token, ministerId, ministry))
                  }
                />
              )}
              {isCM && (
                <SiphonPanel
                  match={match}
                  busy={busy}
                  onSiphon={(amount, cuts) => run("siphon", () => coalitionApi.siphon(matchId, token, amount, cuts))}
                />
              )}
              {!isCM && inGovernment && (
                <div className="p-4" style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}>
                  <PanelTitle icon={<Swords className="h-4 w-4" />} title="Betrayal Option" subtitle="विश्वासघात" accent="var(--pt-red)" />
                  <p className="mt-2 text-xs" style={{ color: "var(--pt-muted)" }}>
                    Not getting cut in on the black money? Withdraw support to collapse the government instantly.
                  </p>
                  <button
                    type="button"
                    disabled={busy === "withdraw"}
                    onClick={() => run("withdraw", () => coalitionApi.withdrawSupport(matchId, token))}
                    className="mt-3 flex h-10 w-full items-center justify-center gap-2 text-xs font-black uppercase disabled:opacity-50"
                    style={{ background: "var(--pt-red)", color: "#fff" }}
                  >
                    🗡️ Withdraw Support
                  </button>
                </div>
              )}
              {!inGovernment && (
                <BlackmailPanel
                  match={match}
                  myPlayerId={myPlayerId}
                  busy={busy}
                  onSend={(targetId, note, demand) =>
                    run("blackmail", () => coalitionApi.blackmail(matchId, token, targetId, note, demand))
                  }
                />
              )}
              <FloorTestPanel
                match={match}
                myPlayerId={myPlayerId}
                busy={busy}
                now={now}
                onTrigger={() => run("floor-trigger", () => coalitionApi.triggerFloorTest(matchId, token))}
                onVote={(vote) => run("floor-vote", () => coalitionApi.castFloorVote(matchId, token, vote))}
              />
            </div>

            {isCM && (
              <button
                type="button"
                disabled={busy === "election"}
                onClick={() => run("election", () => coalitionApi.startElection(matchId, token))}
                className="flex h-11 w-full items-center justify-center gap-2 font-black uppercase disabled:opacity-50"
                style={{ background: "var(--pt-green)", color: "#fff" }}
              >
                <Vote className="h-4 w-4" /> Call the 2029 Election
              </button>
            )}
          </>
        )}

        {/* ── Final Election ────────────────────────────────────── */}
        {match.status === "election" && match.election_result && match.election_started_at && (
          <ElectionRoundsAnnouncer
            startedAt={match.election_started_at}
            rounds={match.election_result.rounds}
            winnerName={match.election_result.winner}
            parties={match.seats.map((s, i) => ({
              name: s.username,
              color: PARTY_COLORS[i % PARTY_COLORS.length],
              finalSeats: match.election_seats_by_player[s.player_id] ?? 0,
            }))}
          />
        )}

        {/* ── Live log ──────────────────────────────────────────── */}
        <div className="p-3" style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}>
          <div className="mb-2 text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>Sansad Ticker — Live Log</div>
          <div className="ledger-scroll grid max-h-40 gap-1 overflow-auto text-xs">
            {match.log.length === 0 ? (
              <span style={{ color: "var(--pt-muted)" }}>Koi ghatna nahi.</span>
            ) : (
              [...match.log].reverse().map((entry, i) => (
                <div key={i} className="px-2 py-1" style={{ borderLeft: "3px solid var(--pt-saffron)", background: "var(--pt-ink)" }}>
                  {entry}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────

function PanelTitle({ icon, title, subtitle, accent }: { icon: React.ReactNode; title: string; subtitle: string; accent: string }) {
  return (
    <div className="flex items-center gap-2 pb-2" style={{ borderBottom: "1px solid var(--pt-line)" }}>
      <span style={{ color: accent }}>{icon}</span>
      <div>
        <div className="text-sm font-black">{title}</div>
        <div className="text-[10px]" style={{ color: "var(--pt-muted)" }}>{subtitle}</div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: CoalitionMatchInfo["status"] }) {
  const labels: Record<string, { label: string; color: string }> = {
    waiting: { label: "Waiting for players", color: "var(--pt-muted)" },
    negotiating: { label: "Negotiating", color: "var(--pt-gold)" },
    governing: { label: "Government Active", color: "var(--pt-green-lt)" },
    floor_test: { label: "Floor Test Live", color: "var(--pt-red-lt)" },
    election: { label: "Election Night", color: "var(--pt-saffron)" },
    finished: { label: "Finished", color: "var(--pt-muted)" },
  };
  const cfg = labels[status] ?? labels.waiting;
  return (
    <span className="px-2 py-1 text-[10px] font-black uppercase" style={{ border: `1px solid ${cfg.color}`, color: cfg.color }}>
      {cfg.label}
    </span>
  );
}

function SeatDistributionBar({ seats, magicNumber, totalSeats }: { seats: CoalitionSeat[]; magicNumber: number; totalSeats: number }) {
  return (
    <div className="p-3" style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}>
      <div className="mb-2 flex items-center justify-between text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>
        <span>Assembly — {totalSeats} seats</span>
        <span>Magic Number: <span style={{ color: "var(--pt-gold)" }}>{magicNumber}</span></span>
      </div>
      <div className="flex h-6 w-full overflow-hidden" style={{ background: "var(--pt-ink)" }}>
        {seats.map((s, i) => (
          <div
            key={s.player_id}
            title={`${s.username} — ${s.party_seats} seats (${s.ideology})`}
            style={{ width: `${(s.party_seats / totalSeats) * 100}%`, background: PARTY_COLORS[i % PARTY_COLORS.length] }}
          />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-3">
        {seats.map((s, i) => (
          <div key={s.player_id} className="flex items-center gap-1 text-[10px]" style={{ color: "var(--pt-muted)" }}>
            <span className="h-2 w-2" style={{ background: PARTY_COLORS[i % PARTY_COLORS.length] }} />
            {s.username} ({s.ideology}) — {s.party_seats}
            {s.role && <span className="ml-1" style={{ color: "var(--pt-gold)" }}>· {s.role}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

function NegotiationPanel({
  match, myPlayerId, busy, onPropose, onRespond, now,
}: {
  match: CoalitionMatchInfo;
  myPlayerId: string;
  busy: string | null;
  onPropose: (partnerIds: string[]) => void;
  onRespond: (proposalId: string, accept: boolean) => void;
  now: number;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const others = match.seats.filter((s) => s.player_id !== myPlayerId);
  const secondsLeft = match.negotiation_deadline ? Math.max(0, Math.round(match.negotiation_deadline - now)) : 0;
  const myProposals = match.pending_proposals.filter((p) => p.proposer_id === myPlayerId);
  const invitesForMe = match.pending_proposals.filter((p) => p.partner_ids.includes(myPlayerId));

  return (
    <div className="p-4" style={{ border: "1px dashed var(--pt-gold)", background: "var(--pt-panel)" }}>
      <PanelTitle icon={<Handshake className="h-4 w-4" />} title="Coalition Negotiation" subtitle="गठबंधन वार्ता — 5 minute window" accent="var(--pt-gold)" />
      <div className="mt-2 text-center text-2xl font-black" style={{ color: secondsLeft < 60 ? "var(--pt-red-lt)" : "var(--pt-gold)" }}>
        {Math.floor(secondsLeft / 60)}:{(secondsLeft % 60).toString().padStart(2, "0")}
      </div>

      <div className="mt-3 text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>Propose a coalition with</div>
      <div className="mt-1 grid gap-1">
        {others.map((s) => (
          <label key={s.player_id} className="flex items-center gap-2 text-xs" style={{ color: "var(--pt-white)" }}>
            <input
              type="checkbox"
              checked={selected.includes(s.player_id)}
              onChange={(e) =>
                setSelected((prev) => (e.target.checked ? [...prev, s.player_id] : prev.filter((id) => id !== s.player_id)))
              }
            />
            {s.username} ({s.party_seats} seats)
          </label>
        ))}
      </div>
      <button
        type="button"
        disabled={busy === "propose" || selected.length === 0}
        onClick={() => onPropose(selected)}
        className="mt-2 flex h-10 w-full items-center justify-center gap-2 text-xs font-black uppercase disabled:opacity-50"
        style={{ background: "var(--pt-gold)", color: "#0C0F14" }}
      >
        Propose Coalition
      </button>

      {invitesForMe.length > 0 && (
        <div className="mt-4 grid gap-2">
          <div className="text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>Invitations for you</div>
          {invitesForMe.map((p) => (
            <div key={p.proposal_id} className="flex items-center justify-between p-2 text-xs" style={{ border: "1px solid var(--pt-line)" }}>
              <span>{match.seats.find((s) => s.player_id === p.proposer_id)?.username} wants you in their coalition</span>
              <div className="flex gap-1">
                <button type="button" onClick={() => onRespond(p.proposal_id, true)} className="px-2 py-1 text-[10px] font-black" style={{ background: "var(--pt-green)", color: "#fff" }}>Accept</button>
                <button type="button" onClick={() => onRespond(p.proposal_id, false)} className="px-2 py-1 text-[10px] font-black" style={{ background: "var(--pt-red)", color: "#fff" }}>Reject</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {myProposals.length > 0 && (
        <div className="mt-3 text-[10px]" style={{ color: "var(--pt-muted)" }}>
          Waiting on: {myProposals.map((p) => p.partner_ids.filter((id) => !p.accepted_by.includes(id)).map((id) => match.seats.find((s) => s.player_id === id)?.username).join(", ")).join(" · ")}
        </div>
      )}
    </div>
  );
}

function GovernmentPanel({ match, myPlayerId, seatById }: { match: CoalitionMatchInfo; myPlayerId: string; seatById: Record<string, CoalitionSeat> }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div className="p-3" style={{ border: "1px solid var(--pt-saffron)", background: "var(--pt-panel)" }}>
        <div className="flex items-center gap-2 text-xs font-black uppercase" style={{ color: "var(--pt-saffron)" }}>
          <Crown className="h-4 w-4" /> Ruling Coalition — {match.government_seat_total}/101
        </div>
        <div className="mt-2 grid gap-1 text-xs">
          {match.government_player_ids.map((pid) => (
            <div key={pid} className="flex items-center justify-between">
              <span>{seatById[pid]?.username} {pid === myPlayerId && <span style={{ color: "var(--pt-gold)" }}>(you)</span>}</span>
              <span style={{ color: "var(--pt-muted)" }}>{seatById[pid]?.role}{seatById[pid]?.ministry ? ` · ${seatById[pid]?.ministry}` : ""}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="p-3" style={{ border: "1px solid var(--pt-red)", background: "var(--pt-panel)" }}>
        <div className="flex items-center gap-2 text-xs font-black uppercase" style={{ color: "var(--pt-red-lt)" }}>
          <ShieldAlert className="h-4 w-4" /> Opposition Bloc
        </div>
        <div className="mt-2 grid gap-1 text-xs">
          {match.opposition_player_ids.length === 0 && <span style={{ color: "var(--pt-muted)" }}>None — total consensus government.</span>}
          {match.opposition_player_ids.map((pid) => (
            <div key={pid} className="flex items-center justify-between">
              <span>{seatById[pid]?.username} {pid === myPlayerId && <span style={{ color: "var(--pt-gold)" }}>(you)</span>}</span>
              <span style={{ color: "var(--pt-muted)" }}>{seatById[pid]?.role}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function MinistryPanel({
  match, busy, onAllocate,
}: { match: CoalitionMatchInfo; busy: string | null; onAllocate: (ministerId: string, ministry: Ministry) => void }) {
  const partners = match.seats.filter((s) => match.government_player_ids.includes(s.player_id) && s.player_id !== match.cm_player_id);
  const [minister, setMinister] = useState(partners[0]?.player_id ?? "");
  const [ministry, setMinistry] = useState<Ministry>("Infrastructure");

  if (partners.length === 0) return null;
  return (
    <div className="p-4" style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}>
      <PanelTitle icon={<Landmark className="h-4 w-4" />} title="Allocate Ministries" subtitle="मंत्रिमंडल — CM only" accent="var(--pt-wheel-lt)" />
      <div className="mt-2 grid gap-2">
        <select value={minister} onChange={(e) => setMinister(e.target.value)} className="h-9 px-2 text-xs" style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)", color: "#fff" }}>
          {partners.map((p) => <option key={p.player_id} value={p.player_id}>{p.username}</option>)}
        </select>
        <div className="grid grid-cols-3 gap-1">
          {(["Infrastructure", "Welfare", "Finance"] as Ministry[]).map((m) => (
            <button
              key={m} type="button" onClick={() => setMinistry(m)}
              className="h-9 text-[10px] font-black uppercase"
              style={ministry === m ? { background: "var(--pt-wheel)", color: "#fff" } : { border: "1px solid var(--pt-line)", color: "var(--pt-muted)" }}
            >
              {m}
            </button>
          ))}
        </div>
        <button
          type="button"
          disabled={busy === "ministry"}
          onClick={() => onAllocate(minister, ministry)}
          className="h-9 text-xs font-black uppercase disabled:opacity-50"
          style={{ background: "var(--pt-wheel)", color: "#fff" }}
        >
          Assign Portfolio
        </button>
      </div>
    </div>
  );
}

function SiphonPanel({
  match, busy, onSiphon,
}: { match: CoalitionMatchInfo; busy: string | null; onSiphon: (amount: number, cuts: Record<string, number>) => void }) {
  const partners = match.seats.filter((s) => match.government_player_ids.includes(s.player_id) && s.player_id !== match.cm_player_id);
  const [amount, setAmount] = useState(500_000);
  const [cuts, setCuts] = useState<Record<string, number>>({});

  return (
    <div className="p-4" style={{ border: "1px solid var(--pt-red)", background: "var(--pt-panel)" }}>
      <PanelTitle icon={<HandCoins className="h-4 w-4" />} title="Siphon Treasury Funds" subtitle="भ्रष्टाचार — Asymmetrical Corruption, CM only" accent="var(--pt-red-lt)" />
      <label className="mt-2 flex items-center justify-between text-xs">
        <span style={{ color: "var(--pt-muted)" }}>Amount (₹)</span>
        <span className="font-black" style={{ color: "var(--pt-red-lt)" }}>₹{amount.toLocaleString("en-IN")}</span>
      </label>
      <input type="range" min={50_000} max={Math.max(50_000, match.treasury)} step={50_000} value={amount} onChange={(e) => setAmount(Number(e.target.value))} className="h-2 w-full" style={{ accentColor: "var(--pt-red)" }} />

      {partners.length > 0 && (
        <div className="mt-3 grid gap-2">
          <div className="text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>Cut partners in (% of siphon)</div>
          {partners.map((p) => (
            <div key={p.player_id} className="flex items-center gap-2 text-xs">
              <span className="w-24 flex-shrink-0 truncate">{p.username}</span>
              <input
                type="range" min={0} max={100} step={5}
                value={Math.round((cuts[p.player_id] ?? 0) * 100)}
                onChange={(e) => setCuts((prev) => ({ ...prev, [p.player_id]: Number(e.target.value) / 100 }))}
                className="h-2 flex-1" style={{ accentColor: "var(--pt-gold)" }}
              />
              <span className="w-10 text-right" style={{ color: "var(--pt-gold)" }}>{Math.round((cuts[p.player_id] ?? 0) * 100)}%</span>
            </div>
          ))}
        </div>
      )}

      <button
        type="button"
        disabled={busy === "siphon"}
        onClick={() => onSiphon(amount, cuts)}
        className="mt-3 flex h-10 w-full items-center justify-center gap-2 text-xs font-black uppercase disabled:opacity-50"
        style={{ background: "var(--pt-red)", color: "#fff" }}
      >
        💰 Siphon & Route Black Money
      </button>
    </div>
  );
}

function BlackmailPanel({
  match, myPlayerId, busy, onSend,
}: { match: CoalitionMatchInfo; myPlayerId: string; busy: string | null; onSend: (targetId: string, note: string, demand: "withdraw_support" | "leak_share") => void }) {
  const targets = match.seats.filter((s) => match.government_player_ids.includes(s.player_id) && s.player_id !== match.cm_player_id);
  const [targetId, setTargetId] = useState(targets[0]?.player_id ?? "");
  const [note, setNote] = useState("I have proof your CM is siphoning funds and keeping it all.");
  const [demand, setDemand] = useState<"withdraw_support" | "leak_share">("withdraw_support");

  if (targets.length === 0) return null;
  return (
    <div className="p-4" style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}>
      <PanelTitle icon={<Gavel className="h-4 w-4" />} title="ED/CBI Blackmail" subtitle="Opposition weaponizes audit findings privately" accent="var(--pt-red-lt)" />
      <select value={targetId} onChange={(e) => setTargetId(e.target.value)} className="mt-2 h-9 w-full px-2 text-xs" style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)", color: "#fff" }}>
        {targets.map((t) => <option key={t.player_id} value={t.player_id}>{t.username}</option>)}
      </select>
      <textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={280} className="mt-2 h-16 w-full resize-none p-2 text-xs" style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)", color: "#fff" }} />
      <select value={demand} onChange={(e) => setDemand(e.target.value as any)} className="mt-2 h-9 w-full px-2 text-xs" style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)", color: "#fff" }}>
        <option value="withdraw_support">Demand: withdraw support</option>
        <option value="leak_share">Demand: leak share of black money</option>
      </select>
      <button
        type="button"
        disabled={busy === "blackmail" || !targetId}
        onClick={() => onSend(targetId, note, demand)}
        className="mt-2 flex h-9 w-full items-center justify-center gap-2 text-xs font-black uppercase disabled:opacity-50"
        style={{ background: "var(--pt-panel-hi)", color: "var(--pt-white)", border: "1px solid var(--pt-red)" }}
      >
        ✉️ Send Private Threat
      </button>
    </div>
  );
}

function FloorTestPanel({
  match, myPlayerId, busy, now, onTrigger, onVote,
}: {
  match: CoalitionMatchInfo;
  myPlayerId: string;
  busy: string | null;
  now: number;
  onTrigger: () => void;
  onVote: (vote: "confidence" | "no_confidence") => void;
}) {
  const cooldownLeft = Math.max(0, Math.round(match.floor_test_cooldown_until - now));
  const active = match.floor_test.active;
  const deadlineLeft = match.floor_test.deadline ? Math.max(0, Math.round(match.floor_test.deadline - now)) : 0;
  const myVote = match.floor_test.votes[myPlayerId];

  return (
    <div className="p-4" style={{ border: active ? "2px solid var(--pt-red)" : "1px solid var(--pt-line)", background: "var(--pt-panel)" }}>
      <PanelTitle icon={<AlertTriangle className="h-4 w-4" />} title="Floor Test" subtitle="विश्वास मत — No-Confidence Motion" accent="var(--pt-red-lt)" />
      {active ? (
        <div className="mt-2">
          <div className="text-center text-xl font-black" style={{ color: "var(--pt-red-lt)" }}>{deadlineLeft}s to vote</div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <button type="button" disabled={busy === "floor-vote" || !!myVote} onClick={() => onVote("confidence")} className="h-10 text-xs font-black uppercase disabled:opacity-50" style={{ background: "var(--pt-green)", color: "#fff" }}>
              {myVote === "confidence" ? "✓ Confidence" : "Vote Confidence"}
            </button>
            <button type="button" disabled={busy === "floor-vote" || !!myVote} onClick={() => onVote("no_confidence")} className="h-10 text-xs font-black uppercase disabled:opacity-50" style={{ background: "var(--pt-red)", color: "#fff" }}>
              {myVote === "no_confidence" ? "✓ No Confidence" : "Vote No-Confidence"}
            </button>
          </div>
          <div className="mt-2 text-[10px]" style={{ color: "var(--pt-muted)" }}>
            {Object.keys(match.floor_test.votes).length}/{match.seats.length} voted
          </div>
        </div>
      ) : (
        <button
          type="button"
          disabled={busy === "floor-trigger" || cooldownLeft > 0}
          onClick={onTrigger}
          className="mt-3 flex h-10 w-full items-center justify-center gap-2 text-xs font-black uppercase disabled:opacity-50"
          style={{ background: "var(--pt-red)", color: "#fff" }}
        >
          {cooldownLeft > 0 ? `Cooldown ${cooldownLeft}s` : "🚨 Call No-Confidence Motion"}
        </button>
      )}
    </div>
  );
}
