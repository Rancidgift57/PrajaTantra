"use client";

import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Factory,
  Leaf,
  Megaphone,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Timer,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";
import { useEffect, useState } from "react";

import {
  ActiveScheme,
  BuildingCatalogEntry,
  BuildingId,
  DevApiClient,
  PlayerRole,
  SchemeCatalogEntry,
  SchemeId,
  SovereignState,
  api,
} from "@/lib/api";

// ── Icon map for building IDs ─────────────────────────────────────────────
const BUILDING_ICONS: Record<BuildingId, string> = {
  PORT:           "🚢",
  MALL:           "🏬",
  FACTORY:        "🏭",
  WASTE_PLANT:    "♻️",
  TECH_PARK:      "💻",
  POWER_GRID:     "⚡",
  SCHOOL_NETWORK: "🏫",
  HOSPITAL_CHAIN: "🏥",
};

const SCHEME_ICONS: Record<SchemeId, string> = {
  SUBSIDY_MSME:        "🏦",
  FREE_HEALTHCARE:     "💊",
  SWACHH_ABHIYAN:      "🧹",
  SKILL_MISSION:       "🎓",
  GREEN_ENERGY_SUBSIDY:"🌱",
  FARMER_LOAN_WAIVER:  "🌾",
};

// ── Portfolio accent colours ──────────────────────────────────────────────
const PORTFOLIO_COLOR: Record<string, string> = {
  Industrial: "var(--pt-saffron)",
  Social:     "var(--pt-green-lt)",
  Strategic:  "var(--pt-wheel-lt)",
};

type Props = {
  role: PlayerRole;
  playerUsername: string;
  onStateUpdate: (state: SovereignState) => void;
  onFlash: (msg: string) => void;
  apiClient?: DevApiClient;
};

export default function CityDevelopment({ role, playerUsername, onStateUpdate, onFlash, apiClient = api }: Props) {
  const [tab, setTab] = useState<"build" | "schemes">("build");
  const [buildings, setBuildings] = useState<BuildingCatalogEntry[]>([]);
  const [schemes, setSchemes]     = useState<SchemeCatalogEntry[]>([]);
  const [activeSchemes, setActiveSchemes] = useState<ActiveScheme[]>([]);
  const [selectedBuilding, setSelectedBuilding] = useState<BuildingCatalogEntry | null>(null);
  const [selectedScheme, setSelectedScheme]     = useState<SchemeCatalogEntry | null>(null);
  const [budget, setBudget]       = useState(400_000);
  const [siphon, setSiphon]       = useState(10);
  const [layerDepth, setLayerDepth] = useState(1);
  const [customName, setCustomName] = useState("");
  const [busy, setBusy]           = useState<string | null>(null);
  const [loadingCatalog, setLoadingCatalog] = useState(true);

  // Load catalogs on mount
  useEffect(() => {
    Promise.all([
      apiClient.buildingCatalog(),
      apiClient.schemeCatalog(),
      apiClient.activeSchemes(),
    ]).then(([bCat, sCat, active]) => {
      setBuildings(bCat.buildings);
      setSchemes(sCat.schemes);
      setActiveSchemes(active);
      setSelectedBuilding(bCat.buildings[0] ?? null);
      setSelectedScheme(sCat.schemes[0] ?? null);
    }).catch(() => {
      onFlash("⚠️ Development catalog load karne mein samasya aayi.");
    }).finally(() => setLoadingCatalog(false));
  }, [apiClient]);

  async function handleBuild() {
    if (!selectedBuilding || role !== "Incumbent") return;
    setBusy("build");
    try {
      const res = await apiClient.buildFromCatalog({
        role,
        player_username: playerUsername,
        building_id: selectedBuilding.id,
        custom_name: customName.trim() || undefined,
        budget,
        siphon_percent: siphon,
        layer_depth: layerDepth,
      });
      onStateUpdate(res.state);
      onFlash(`🏗️ ${res.message}`);
      setCustomName("");
    } catch (err) {
      onFlash(err instanceof Error ? `❌ ${err.message}` : "❌ Nirman asafal.");
    } finally {
      setBusy(null);
    }
  }

  async function handleLaunchScheme() {
    if (!selectedScheme || role !== "Incumbent") return;
    setBusy("scheme");
    try {
      const res = await apiClient.launchScheme({ role, scheme_id: selectedScheme.id });
      onStateUpdate(res.state);
      setActiveSchemes((prev) => [...prev.filter((s) => s.scheme_id !== res.active_scheme.scheme_id), res.active_scheme]);
      onFlash(`📋 ${res.message}`);
    } catch (err) {
      onFlash(err instanceof Error ? `❌ ${err.message}` : "❌ Yojana asafal.");
    } finally {
      setBusy(null);
    }
  }

  const isLocked = role !== "Incumbent";
  const minBudget = selectedBuilding?.base_cost ?? 100_000;
  const effectiveBudget = Math.max(budget, minBudget);

  if (loadingCatalog) {
    return (
      <div className="flex items-center justify-center p-8 text-sm" style={{ color: "var(--pt-muted)" }}>
        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
        Catalog lod ho raha hai…
      </div>
    );
  }

  return (
    <div style={{ color: "var(--pt-white)" }}>
      {/* Tab switcher */}
      <div className="mb-4 grid grid-cols-2 p-1" style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)" }}>
        <TabBtn active={tab === "build"} onClick={() => setTab("build")} icon="🏗️" label="Shehar Nirmaan" hint="City Buildings" />
        <TabBtn active={tab === "schemes"} onClick={() => setTab("schemes")} icon="📋" label="Sarkari Yojana" hint="Gov Schemes" />
      </div>

      {isLocked && (
        <div className="mb-3 px-3 py-2 text-xs font-bold" style={{ border: "1px solid var(--pt-red)", color: "var(--pt-red-lt)", background: "var(--pt-ink)" }}>
          🔒 Sirf Incumbent hi shehar viksit kar sakta hai. Role badlein.
        </div>
      )}

      {/* ── BUILD TAB ─────────────────────────────────────────────────── */}
      {tab === "build" && (
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          {/* Building grid */}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {buildings.map((b) => (
              <BuildingCard
                key={b.id}
                building={b}
                selected={selectedBuilding?.id === b.id}
                onSelect={() => {
                  setSelectedBuilding(b);
                  setBudget(Math.max(budget, b.base_cost));
                }}
              />
            ))}
          </div>

          {/* Config panel */}
          {selectedBuilding && (
            <div className="flex flex-col gap-3">
              {/* Selected building summary */}
              <div className="p-3" style={{ background: "var(--pt-ink)", border: `1px solid ${PORTFOLIO_COLOR[selectedBuilding.portfolio_type]}` }}>
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{BUILDING_ICONS[selectedBuilding.id]}</span>
                  <div>
                    <div className="font-black text-sm">{selectedBuilding.name}</div>
                    <div className="text-[10px]" style={{ color: PORTFOLIO_COLOR[selectedBuilding.portfolio_type] }}>
                      {selectedBuilding.hindi_name} · {selectedBuilding.portfolio_type}
                    </div>
                  </div>
                </div>
                <p className="mt-2 text-xs leading-5" style={{ color: "var(--pt-muted)" }}>
                  {selectedBuilding.description}
                </p>

                {/* Tradeoff stats */}
                <div className="mt-3 grid grid-cols-2 gap-1">
                  <StatChip label="Gold/tick"     value={`₹${(selectedBuilding.gold_per_tick/1000).toFixed(0)}K`} positive />
                  <StatChip label="Maintenance"   value={`₹${(selectedBuilding.maintenance/1000).toFixed(0)}K`}  positive={false} />
                  <StatChip label="Trust"         value={selectedBuilding.trust_delta}         isNumber />
                  <StatChip label="Pollution"     value={selectedBuilding.pollution_delta}     isNumber invert />
                  <StatChip label="Unrest"        value={selectedBuilding.unrest_delta}        isNumber invert />
                  <StatChip label="Employment"    value={selectedBuilding.employment_delta}    isNumber />
                  <StatChip label="Prestige"      value={selectedBuilding.prestige_delta}      isNumber />
                  <StatChip label="Min Budget"    value={`₹${(selectedBuilding.base_cost/1e5).toFixed(1)}L`} positive />
                </div>

                {/* Pros/Cons */}
                <div className="mt-3 grid grid-cols-2 gap-2 text-[10px]">
                  <div>
                    {selectedBuilding.pros.map((p) => (
                      <div key={p} className="flex items-start gap-1 mb-1" style={{ color: "var(--pt-green-lt)" }}>
                        <CheckCircle2 className="h-3 w-3 mt-0.5 flex-shrink-0" />{p}
                      </div>
                    ))}
                  </div>
                  <div>
                    {selectedBuilding.cons.map((c) => (
                      <div key={c} className="flex items-start gap-1 mb-1" style={{ color: "var(--pt-red-lt)" }}>
                        <AlertTriangle className="h-3 w-3 mt-0.5 flex-shrink-0" />{c}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Build controls */}
              <div className="grid gap-2 p-3" style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)" }}>
                <label className="grid gap-1">
                  <span className="text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>Custom Name (optional)</span>
                  <input
                    value={customName}
                    onChange={(e) => setCustomName(e.target.value)}
                    placeholder={selectedBuilding.name}
                    className="h-9 px-2 text-sm outline-none"
                    style={{ background: "var(--pt-panel)", border: "1px solid var(--pt-line)", color: "var(--pt-white)" }}
                  />
                </label>
                <SliderRow label="Budget" hindi="बजट" value={effectiveBudget} min={selectedBuilding.base_cost} max={2_000_000} step={10_000}
                  onChange={setBudget} color="var(--pt-saffron)" fmt={(v) => `₹${(v/1e5).toFixed(1)}L`} />
                <SliderRow label="Corruption %" hindi="भ्रष्टाचार" value={siphon} min={0} max={60} step={5}
                  onChange={setSiphon} color="var(--pt-red)" fmt={(v) => `${v}%`} />
                <SliderRow label="Cover Layers" hindi="परतें" value={layerDepth} min={1} max={6} step={1}
                  onChange={setLayerDepth} color="var(--pt-wheel-lt)" fmt={(v) => `${v}`} />
              </div>

              <button
                type="button"
                onClick={handleBuild}
                disabled={busy === "build" || isLocked}
                className="flex h-12 w-full items-center justify-center gap-2 font-black uppercase disabled:opacity-40"
                style={{ background: "var(--pt-saffron)", color: "#fff", border: "none" }}
              >
                <Building2 className="h-5 w-5" />
                {busy === "build" ? "Nirman Ho Raha Hai…" : `${BUILDING_ICONS[selectedBuilding.id]} ${selectedBuilding.name} Banao`}
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── SCHEMES TAB ──────────────────────────────────────────────── */}
      {tab === "schemes" && (
        <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
          {/* Scheme list */}
          <div className="grid gap-2">
            {schemes.map((s) => {
              const isActive = activeSchemes.some((a) => a.scheme_id === s.id);
              return (
                <SchemeCard
                  key={s.id}
                  scheme={s}
                  selected={selectedScheme?.id === s.id}
                  isActive={isActive}
                  onSelect={() => !isActive && setSelectedScheme(s)}
                />
              );
            })}
          </div>

          {/* Scheme detail + launch */}
          <div className="flex flex-col gap-3">
            {/* Active schemes status */}
            {activeSchemes.length > 0 && (
              <div className="p-3" style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-green)" }}>
                <div className="mb-2 text-[10px] uppercase font-bold" style={{ color: "var(--pt-green-lt)" }}>
                  ✅ Chal Rahi Yojanaen ({activeSchemes.length})
                </div>
                {activeSchemes.map((a) => (
                  <div key={a.scheme_id} className="mb-2 flex items-center justify-between text-xs">
                    <span>{SCHEME_ICONS[a.scheme_id]} {a.name}</span>
                    <span className="flex items-center gap-1" style={{ color: "var(--pt-gold)" }}>
                      <Timer className="h-3 w-3" />{a.cycles_remaining}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Selected scheme detail */}
            {selectedScheme && (
              <div className="p-3" style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-wheel)" }}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-2xl">{SCHEME_ICONS[selectedScheme.id]}</span>
                  <div>
                    <div className="font-black text-sm">{selectedScheme.name}</div>
                    <div className="text-[10px]" style={{ color: "var(--pt-wheel-lt)" }}>{selectedScheme.hindi_name}</div>
                  </div>
                </div>
                <p className="text-xs leading-5 mb-3" style={{ color: "var(--pt-muted)" }}>{selectedScheme.description}</p>

                <div className="grid grid-cols-2 gap-1 mb-3">
                  <StatChip label="Upfront Cost"   value={`₹${(selectedScheme.upfront_cost/1e5).toFixed(1)}L`}      positive={false} />
                  <StatChip label="Cost/Cycle"     value={`₹${(selectedScheme.cost_per_tick/1000).toFixed(0)}K`}     positive={false} />
                  <StatChip label="Duration"       value={`${selectedScheme.duration_cycles} cycles`}                positive />
                  <StatChip label="GDP Impact"     value={`${selectedScheme.gdp_multiplier_percent > 0 ? "+" : ""}${selectedScheme.gdp_multiplier_percent}%`} positive={selectedScheme.gdp_multiplier_percent >= 0} />
                  <StatChip label="Trust"          value={selectedScheme.trust_delta}        isNumber />
                  <StatChip label="Unrest"         value={selectedScheme.unrest_delta}       isNumber invert />
                  <StatChip label="Employment"     value={selectedScheme.employment_delta}   isNumber />
                  <StatChip label="Pollution"      value={selectedScheme.pollution_delta}    isNumber invert />
                </div>

                <div className="grid grid-cols-2 gap-2 text-[10px] mb-3">
                  <div>
                    {selectedScheme.pros.map((p) => (
                      <div key={p} className="flex items-start gap-1 mb-1" style={{ color: "var(--pt-green-lt)" }}>
                        <CheckCircle2 className="h-3 w-3 mt-0.5 flex-shrink-0" />{p}
                      </div>
                    ))}
                  </div>
                  <div>
                    {selectedScheme.cons.map((c) => (
                      <div key={c} className="flex items-start gap-1 mb-1" style={{ color: "var(--pt-red-lt)" }}>
                        <AlertTriangle className="h-3 w-3 mt-0.5 flex-shrink-0" />{c}
                      </div>
                    ))}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleLaunchScheme}
                  disabled={busy === "scheme" || isLocked || activeSchemes.some((a) => a.scheme_id === selectedScheme.id)}
                  className="flex h-11 w-full items-center justify-center gap-2 font-black uppercase disabled:opacity-40"
                  style={{ background: "var(--pt-wheel)", color: "#fff", border: "none" }}
                >
                  <Megaphone className="h-4 w-4" />
                  {busy === "scheme" ? "Laagu Ho Raha Hai…" :
                   activeSchemes.some((a) => a.scheme_id === selectedScheme.id) ? "Already Active ✅" :
                   "Yojana Laagu Karein"}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────

function TabBtn({ active, onClick, icon, label, hint }: {
  active: boolean; onClick: () => void; icon: string; label: string; hint: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col items-center justify-center gap-0.5 py-2 text-xs font-black uppercase transition-all"
      style={active ? { background: "var(--pt-saffron)", color: "#fff" } : { color: "var(--pt-muted)" }}
    >
      <span>{icon} {label}</span>
      <span className="text-[9px] font-normal normal-case opacity-70">{hint}</span>
    </button>
  );
}

function BuildingCard({ building, selected, onSelect }: {
  building: BuildingCatalogEntry; selected: boolean; onSelect: () => void;
}) {
  const accent = PORTFOLIO_COLOR[building.portfolio_type];
  const netRev = building.gold_per_tick - building.maintenance;
  return (
    <button
      type="button"
      onClick={onSelect}
      className="p-3 text-left transition-all"
      style={{
        background: "var(--pt-ink)",
        border: `1px solid ${selected ? accent : "var(--pt-line)"}`,
        boxShadow: selected ? `0 0 0 2px ${accent}30` : "none",
      }}
    >
      <div className="text-xl mb-1">{BUILDING_ICONS[building.id]}</div>
      <div className="text-xs font-black leading-tight">{building.name}</div>
      <div className="text-[9px] mt-0.5" style={{ color: accent }}>{building.hindi_name}</div>
      <div className="mt-2 text-[10px]" style={{ color: "var(--pt-muted)" }}>
        <div>₹{(building.base_cost / 1e5).toFixed(1)}L min</div>
        <div style={{ color: netRev >= 0 ? "var(--pt-green-lt)" : "var(--pt-red-lt)" }}>
          Net {netRev >= 0 ? "+" : ""}₹{(netRev / 1000).toFixed(0)}K
        </div>
      </div>
    </button>
  );
}

function SchemeCard({ scheme, selected, isActive, onSelect }: {
  scheme: SchemeCatalogEntry; selected: boolean; isActive: boolean; onSelect: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="p-3 cursor-pointer transition-all"
      onClick={onSelect}
      style={{
        background: "var(--pt-ink)",
        border: `1px solid ${selected ? "var(--pt-wheel)" : "var(--pt-line)"}`,
        opacity: isActive ? 0.6 : 1,
      }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">{SCHEME_ICONS[scheme.id]}</span>
          <div>
            <div className="text-sm font-black">{scheme.name}</div>
            <div className="text-[10px]" style={{ color: "var(--pt-muted)" }}>{scheme.hindi_name}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isActive && <span className="text-[9px] font-bold px-1" style={{ background: "var(--pt-green)", color: "#fff" }}>LIVE</span>}
          <div className="text-right text-[10px]" style={{ color: "var(--pt-muted)" }}>
            <div>₹{(scheme.upfront_cost / 1e5).toFixed(1)}L</div>
            <div>{scheme.duration_cycles}c</div>
          </div>
          <button type="button" onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }} style={{ color: "var(--pt-muted)" }}>
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>
      {expanded && (
        <div className="mt-2 pt-2 text-[10px]" style={{ borderTop: "1px solid var(--pt-line)", color: "var(--pt-muted)" }}>
          <div className="mb-1">{scheme.description}</div>
          <div className="grid grid-cols-4 gap-1 mt-2">
            <SmallStat label="Trust"  value={scheme.trust_delta}        positive={scheme.trust_delta >= 0} />
            <SmallStat label="Unrest" value={scheme.unrest_delta}       positive={scheme.unrest_delta <= 0} />
            <SmallStat label="Jobs"   value={scheme.employment_delta}   positive={scheme.employment_delta >= 0} />
            <SmallStat label="GDP"    value={`${scheme.gdp_multiplier_percent}%`} positive={scheme.gdp_multiplier_percent >= 0} />
          </div>
        </div>
      )}
    </div>
  );
}

function StatChip({ label, value, isNumber = false, positive, invert = false }: {
  label: string; value: number | string; isNumber?: boolean; positive?: boolean; invert?: boolean;
}) {
  let color = "var(--pt-muted)";
  if (isNumber && typeof value === "number") {
    const good = invert ? value < 0 : value > 0;
    color = value === 0 ? "var(--pt-muted)" : good ? "var(--pt-green-lt)" : "var(--pt-red-lt)";
  } else if (typeof positive === "boolean") {
    color = positive ? "var(--pt-green-lt)" : "var(--pt-red-lt)";
  }
  const display = isNumber && typeof value === "number"
    ? `${value > 0 ? "+" : ""}${value}`
    : value;
  return (
    <div className="px-2 py-1" style={{ background: "var(--pt-panel)", border: "1px solid var(--pt-line)" }}>
      <div className="text-[9px] uppercase" style={{ color: "var(--pt-muted)" }}>{label}</div>
      <div className="text-xs font-black" style={{ color }}>{display}</div>
    </div>
  );
}

function SmallStat({ label, value, positive }: { label: string; value: number | string; positive: boolean }) {
  return (
    <div className="text-center">
      <div style={{ color: "var(--pt-muted)" }}>{label}</div>
      <div className="font-black" style={{ color: positive ? "var(--pt-green-lt)" : "var(--pt-red-lt)" }}>
        {typeof value === "number" ? (value > 0 ? `+${value}` : `${value}`) : value}
      </div>
    </div>
  );
}

function SliderRow({ label, hindi, value, min, max, step, onChange, color, fmt }: {
  label: string; hindi: string; value: number; min: number; max: number; step: number;
  onChange: (v: number) => void; color: string; fmt: (v: number) => string;
}) {
  return (
    <label className="grid gap-1">
      <span className="flex justify-between text-[10px]">
        <span style={{ color: "var(--pt-muted)" }}>{label} <span style={{ opacity: 0.6 }}>· {hindi}</span></span>
        <span className="font-black" style={{ color }}>{fmt(value)}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-2" style={{ accentColor: color }} />
    </label>
  );
}