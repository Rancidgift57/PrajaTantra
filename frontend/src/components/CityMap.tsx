"use client";

/**
 * CityMap — Interactive City Planning Map for PrajaTantra
 *
 * An 8×8 zoned grid representing Bangalore. Players click a zone to place a
 * building from the catalog on it — zone type constrains which buildings are
 * allowed (Port only on Water/Industrial, Hospital only on Residential/
 * Government, etc.). Placed buildings are submitted to the real backend via
 * /api/development/buildings/build so they actually affect city stats.
 *
 * Visual features:
 *  - Zone colours distinguishing Residential / Industrial / Commercial /
 *    Strategic / Green / Water / Road / Government
 *  - Pollution heat overlay — high-pollution buildings bleed orange haze
 *    into adjacent cells
 *  - Building emoji rendered on placed cells
 *  - Hover tooltip with zone name, building slot, zone rules
 *  - "City Health" mini-bar showing aggregate pollution / trust / employment
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActiveScheme,
  BuildingCatalogEntry,
  BuildingId,
  DevApiClient,
  PlayerRole,
  SovereignState,
  api,
} from "@/lib/api";

// ── Zone definitions ────────────────────────────────────────────────────────

type ZoneType =
  | "RESIDENTIAL" | "INDUSTRIAL" | "COMMERCIAL" | "STRATEGIC"
  | "GREEN"       | "ROAD"       | "WATER"      | "GOVERNMENT";

const ZONE_META: Record<ZoneType, {
  label: string; hindi: string; color: string; allowedBuildings: BuildingId[];
}> = {
  RESIDENTIAL: {
    label: "Residential",  hindi: "आवासीय",
    color: "#253550",
    allowedBuildings: ["HOSPITAL_CHAIN", "SCHOOL_NETWORK", "MALL"],
  },
  INDUSTRIAL: {
    label: "Industrial",   hindi: "औद्योगिक",
    color: "#5C3A1A",
    allowedBuildings: ["PORT", "FACTORY", "WASTE_PLANT"],
  },
  COMMERCIAL: {
    label: "Commercial",   hindi: "वाणिज्यिक",
    color: "#6B5010",
    allowedBuildings: ["MALL", "TECH_PARK"],
  },
  STRATEGIC: {
    label: "Strategic",    hindi: "रणनीतिक",
    color: "#152A4A",
    allowedBuildings: ["TECH_PARK", "POWER_GRID"],
  },
  GREEN: {
    label: "Green Zone",   hindi: "हरित क्षेत्र",
    color: "#143A1E",
    allowedBuildings: ["WASTE_PLANT", "SCHOOL_NETWORK", "POWER_GRID"],
  },
  ROAD: {
    label: "Road",         hindi: "सड़क",
    color: "#1A1A1A",
    allowedBuildings: [],
  },
  WATER: {
    label: "Water",        hindi: "जल क्षेत्र",
    color: "#0A2540",
    allowedBuildings: ["PORT"],
  },
  GOVERNMENT: {
    label: "Government",   hindi: "सरकारी",
    color: "#2A1040",
    allowedBuildings: ["HOSPITAL_CHAIN", "SCHOOL_NETWORK"],
  },
};

const BUILDING_EMOJI: Record<BuildingId, string> = {
  PORT:           "🚢", MALL:           "🏬",
  FACTORY:        "🏭", WASTE_PLANT:    "♻️",
  TECH_PARK:      "💻", POWER_GRID:     "⚡",
  SCHOOL_NETWORK: "🏫", HOSPITAL_CHAIN: "🏥",
};

const BUILDING_POLLUTION: Record<BuildingId, number> = {
  PORT: 16, MALL: 3, FACTORY: 12, WASTE_PLANT: -18,
  TECH_PARK: 1, POWER_GRID: -8, SCHOOL_NETWORK: -1, HOSPITAL_CHAIN: -2,
};

// ── Default 8×8 Bangalore city grid ────────────────────────────────────────

const DEFAULT_GRID: ZoneType[][] = [
  ["ROAD",       "COMMERCIAL",  "COMMERCIAL",  "ROAD",        "GOVERNMENT",  "RESIDENTIAL", "RESIDENTIAL", "ROAD"],
  ["INDUSTRIAL", "INDUSTRIAL",  "ROAD",        "RESIDENTIAL", "RESIDENTIAL", "RESIDENTIAL", "ROAD",        "GREEN"],
  ["INDUSTRIAL", "INDUSTRIAL",  "ROAD",        "RESIDENTIAL", "RESIDENTIAL", "ROAD",        "GREEN",       "GREEN"],
  ["ROAD",       "ROAD",        "ROAD",        "ROAD",        "ROAD",        "ROAD",        "ROAD",        "ROAD"],
  ["GREEN",      "COMMERCIAL",  "COMMERCIAL",  "ROAD",        "RESIDENTIAL", "RESIDENTIAL", "RESIDENTIAL", "ROAD"],
  ["GREEN",      "COMMERCIAL",  "ROAD",        "STRATEGIC",   "STRATEGIC",   "ROAD",        "RESIDENTIAL", "ROAD"],
  ["WATER",      "WATER",       "INDUSTRIAL",  "ROAD",        "GREEN",       "GREEN",       "ROAD",        "RESIDENTIAL"],
  ["WATER",      "WATER",       "WATER",       "ROAD",        "GREEN",       "ROAD",        "ROAD",        "COMMERCIAL"],
];

// The 8x8 grid split into 4 wards (quadrants) for the Live Seat Projection's
// ward-level volatility: concentrating buildings in one quadrant spikes
// that ward's local pollution/unrest and swings its seat share.
//   cols 0-3      cols 4-7
//   ┌───────────┬───────────┐
//   │   North   │   East    │  rows 0-3
//   ├───────────┼───────────┤
//   │   West    │   South   │  rows 4-7
//   └───────────┴───────────┘
function wardFor(row: number, col: number): "North" | "East" | "South" | "West" {
  const top = row < 4;
  const left = col < 4;
  if (top && left) return "North";
  if (top && !left) return "East";
  if (!top && !left) return "South";
  return "West";
}

// ── Types ───────────────────────────────────────────────────────────────────

type PlacedBuilding = {
  buildingId: BuildingId;
  name: string;
  row: number;
  col: number;
  placedAt: string; // ISO timestamp
};

type MapState = {
  placed: PlacedBuilding[];
};

const MAP_STORAGE_KEY = "prajatantra.citymap.v1";

// ── Props ───────────────────────────────────────────────────────────────────

type Props = {
  role: PlayerRole;
  playerUsername: string;
  cityState: SovereignState | null;
  onStateUpdate: (s: SovereignState) => void;
  onFlash: (msg: string) => void;
  apiClient?: DevApiClient;
};

// ── Component ───────────────────────────────────────────────────────────────

export default function CityMap({
  role, playerUsername, cityState, onStateUpdate, onFlash, apiClient = api,
}: Props) {
  const [catalog, setCatalog]             = useState<BuildingCatalogEntry[]>([]);
  const [mapState, setMapState]           = useState<MapState>({ placed: [] });
  const [selectedBuilding, setSelectedBuilding] = useState<BuildingCatalogEntry | null>(null);
  const [hoveredCell, setHoveredCell]     = useState<{ row: number; col: number } | null>(null);
  const [busyCell, setBusyCell]           = useState<string | null>(null);
  const [budget, setBudget]               = useState(400_000);
  const [siphon, setSiphon]               = useState(10);
  const [showOverlay, setShowOverlay]     = useState<"pollution" | "zone" | "none">("zone");

  // Load catalog + stored map state
  useEffect(() => {
    apiClient.buildingCatalog().then((r) => {
      setCatalog(r.buildings);
      setSelectedBuilding(r.buildings[0] ?? null);
    }).catch(() => onFlash("⚠️ Building catalog load failed."));

    try {
      const raw = localStorage.getItem(MAP_STORAGE_KEY);
      if (raw) setMapState(JSON.parse(raw));
    } catch { /* start fresh */ }
  }, [apiClient]);

  function saveMapState(next: MapState) {
    setMapState(next);
    try { localStorage.setItem(MAP_STORAGE_KEY, JSON.stringify(next)); } catch { /* ignore */ }
  }

  // Compute per-cell pollution levels for heat overlay
  const pollutionGrid: number[][] = DEFAULT_GRID.map((row, r) =>
    row.map((_, c) => {
      const placed = mapState.placed.filter((p) => p.row === r && p.col === c);
      let baseVal = placed.reduce((sum, p) => sum + (BUILDING_POLLUTION[p.buildingId] ?? 0), 0);
      // Bleed from neighbours
      const neighbors = [[-1,0],[1,0],[0,-1],[0,1]];
      for (const [dr, dc] of neighbors) {
        const nr = r + dr; const nc = c + dc;
        if (nr < 0 || nr >= 8 || nc < 0 || nc >= 8) continue;
        mapState.placed
          .filter((p) => p.row === nr && p.col === nc && (BUILDING_POLLUTION[p.buildingId] ?? 0) > 0)
          .forEach((p) => { baseVal += (BUILDING_POLLUTION[p.buildingId] ?? 0) * 0.3; });
      }
      return Math.max(-20, Math.min(30, baseVal));
    })
  );

  // Check if selected building can be placed on a cell
  function canPlace(row: number, col: number): "ok" | "zone" | "occupied" | "locked" {
    if (role !== "Incumbent") return "locked";
    if (!selectedBuilding) return "locked";
    const zone = DEFAULT_GRID[row][col];
    const zoneAllows = ZONE_META[zone].allowedBuildings.includes(selectedBuilding.id);
    // 🚨 Emergency powers (declared after an 80%+ seat supermajority) let
    // Industrial-zone buildings bypass Residential zoning entirely — a
    // deliberate authoritarian-overreach mechanic.
    const emergencyOverride =
      cityState?.emergency_powers === true &&
      zone === "RESIDENTIAL" &&
      ZONE_META.INDUSTRIAL.allowedBuildings.includes(selectedBuilding.id);
    if (!zoneAllows && !emergencyOverride) return "zone";
    if (mapState.placed.some((p) => p.row === row && p.col === col)) return "occupied";
    return "ok";
  }

  async function handleCellClick(row: number, col: number) {
    const status = canPlace(row, col);
    if (status === "locked") { onFlash("🔒 Sirf Incumbent shehar bana sakta hai."); return; }
    if (status === "zone")   { 
      const zone = DEFAULT_GRID[row][col];
      const allowed = ZONE_META[zone].allowedBuildings;
      const hint = cityState?.emergency_powers
        ? ""
        : " 🚨 Emergency powers (80%+ seats) would let Industrial buildings bypass Residential zoning.";
      onFlash(`❌ ${selectedBuilding?.name} ko ${ZONE_META[zone].label} zone mein nahi banaya ja sakta. Allowed: ${allowed.join(", ") || "kuch nahi"}.${hint}`);
      return;
    }
    if (status === "occupied") { onFlash("⚠️ Yeh cell pehle se occupied hai."); return; }
    if (!selectedBuilding) return;

    const cellKey = `${row}-${col}`;
    setBusyCell(cellKey);
    try {
      const res = await apiClient.buildFromCatalog({
        role,
        player_username: playerUsername,
        building_id: selectedBuilding.id,
        budget: Math.max(budget, selectedBuilding.base_cost),
        siphon_percent: siphon,
        layer_depth: 1,
        ward: wardFor(row, col),
      });
      onStateUpdate(res.state);
      const next: MapState = {
        placed: [...mapState.placed, {
          buildingId: selectedBuilding.id,
          name: selectedBuilding.name,
          row,
          col,
          placedAt: new Date().toISOString(),
        }],
      };
      saveMapState(next);
      onFlash(`🏗️ ${BUILDING_EMOJI[selectedBuilding.id]} ${selectedBuilding.name} placed at [${row},${col}] — ${res.message}`);
    } catch (err) {
      onFlash(err instanceof Error ? `❌ ${err.message}` : "❌ Build failed.");
    } finally {
      setBusyCell(null);
    }
  }

  function removeBuilding(row: number, col: number) {
    const next: MapState = {
      placed: mapState.placed.filter((p) => !(p.row === row && p.col === col)),
    };
    saveMapState(next);
    onFlash("🗑️ Building map se hatayi gayi (city stats unchanged — backend pe record remain karta hai).");
  }

  // City health summary from live state
  const pollution   = cityState?.city?.pollution ?? 0;
  const trust       = cityState?.city?.public_trust ?? 0;
  const unemployment = cityState?.city?.unemployment ?? 0;
  const totalBuilt  = mapState.placed.length;

  return (
    <div>
      {cityState?.emergency_powers && (
        <div
          className="mb-3 flex items-center gap-2 px-3 py-2 text-[11px] font-black"
          style={{ background: "rgba(192,41,42,0.12)", border: "1px solid var(--pt-red)", color: "var(--pt-red-lt)" }}
        >
          🚨 Aapatkaal Laagu — Industrial buildings (Factory, Port, Waste Plant) can now be built directly on Residential zones.
        </div>
      )}

      {/* Header controls row */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
          {(["zone", "pollution", "none"] as const).map((o) => (
            <button
              key={o}
              type="button"
              onClick={() => setShowOverlay(o)}
              className="px-2 py-1 text-[10px] font-bold uppercase"
              style={showOverlay === o
                ? { background: "var(--pt-saffron)", color: "#fff" }
                : { border: "1px solid var(--pt-line)", color: "var(--pt-muted)" }}
            >
              {o === "zone" ? "🗺️ Zone" : o === "pollution" ? "🌫️ Pollution" : "📐 Clean"}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-4 text-xs">
          <HealthBar label="Pollution"    value={pollution}    color={pollution > 50 ? "var(--pt-red)" : "var(--pt-gold)"} invert />
          <HealthBar label="Jan Vishwas"  value={trust}        color="var(--pt-green-lt)" />
          <HealthBar label="Rozgaar"      value={100 - unemployment} color="var(--pt-wheel-lt)" />
          <span style={{ color: "var(--pt-muted)" }}>{totalBuilt} buildings placed</span>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        {/* ── Grid ──────────────────────────────────────────────────── */}
        <div>
          {/* Column labels */}
          <div className="grid mb-1" style={{ gridTemplateColumns: "24px repeat(8, 1fr)", gap: "2px" }}>
            <div />
            {["A","B","C","D","E","F","G","H"].map((c) => (
              <div key={c} className="text-center text-[9px]" style={{ color: "var(--pt-muted)" }}>{c}</div>
            ))}
          </div>

          {DEFAULT_GRID.map((row, r) => (
            <div key={r} className="grid mb-[2px]" style={{ gridTemplateColumns: "24px repeat(8, 1fr)", gap: "2px" }}>
              {/* Row label */}
              <div className="flex items-center justify-center text-[9px]" style={{ color: "var(--pt-muted)" }}>{r + 1}</div>

              {row.map((zone, c) => {
                const placed = mapState.placed.find((p) => p.row === r && p.col === c);
                const isHovered = hoveredCell?.row === r && hoveredCell?.col === c;
                const status = canPlace(r, c);
                const isBusy = busyCell === `${r}-${c}`;
                const pollVal = pollutionGrid[r][c];

                // Cell background
                let bg = ZONE_META[zone].color;
                if (showOverlay === "pollution") {
                  if (pollVal > 10) bg = `rgba(192,41,42,${Math.min(0.8, pollVal / 30)})`;
                  else if (pollVal > 0) bg = `rgba(201,150,45,${pollVal / 15})`;
                  else if (pollVal < 0) bg = `rgba(19,138,54,${Math.min(0.7, Math.abs(pollVal) / 20)})`;
                }
                const borderColor = isHovered && status === "ok"
                  ? "var(--pt-saffron)"
                  : placed
                  ? "rgba(255,255,255,0.2)"
                  : "transparent";

                return (
                  <div
                    key={c}
                    onClick={() => !isBusy && handleCellClick(r, c)}
                    onMouseEnter={() => setHoveredCell({ row: r, col: c })}
                    onMouseLeave={() => setHoveredCell(null)}
                    onContextMenu={(e) => { e.preventDefault(); if (placed) removeBuilding(r, c); }}
                    className="relative flex items-center justify-center transition-all"
                    style={{
                      background: bg,
                      border: `1px solid ${borderColor}`,
                      height: "52px",
                      cursor: zone === "ROAD" ? "default" :
                              status === "ok" ? "crosshair" : "not-allowed",
                      boxShadow: isHovered && status === "ok"
                        ? "0 0 0 2px var(--pt-saffron)" : "none",
                    }}
                    title={`[${r+1}${["A","B","C","D","E","F","G","H"][c]}] ${ZONE_META[zone].label}`}
                  >
                    {isBusy ? (
                      <div className="text-base animate-spin">⏳</div>
                    ) : placed ? (
                      <div className="flex flex-col items-center">
                        <div className="text-lg leading-none">{BUILDING_EMOJI[placed.buildingId]}</div>
                        <div className="text-[7px] leading-none mt-0.5" style={{ color: "rgba(255,255,255,0.6)" }}>
                          {placed.name.split(" ")[0]}
                        </div>
                      </div>
                    ) : showOverlay === "zone" && zone !== "ROAD" ? (
                      <div className="text-[8px] text-center px-0.5" style={{ color: "rgba(255,255,255,0.25)", lineHeight: 1.2 }}>
                        {ZONE_META[zone].hindi}
                      </div>
                    ) : null}

                    {/* Pollution value in pollution view */}
                    {showOverlay === "pollution" && pollVal !== 0 && (
                      <div
                        className="absolute bottom-0.5 right-0.5 text-[8px] font-black"
                        style={{ color: pollVal > 0 ? "var(--pt-red-lt)" : "var(--pt-green-lt)" }}
                      >
                        {pollVal > 0 ? "+" : ""}{Math.round(pollVal)}
                      </div>
                    )}

                    {/* Hover: show zone allowed buildings */}
                    {isHovered && !placed && status !== "locked" && (
                      <div
                        className="absolute bottom-full left-0 z-50 mb-1 min-w-[110px] px-2 py-1 text-[9px] leading-4"
                        style={{ background: "var(--pt-panel)", border: "1px solid var(--pt-line)", whiteSpace: "nowrap" }}
                      >
                        <div className="font-bold" style={{ color: "var(--pt-saffron)" }}>{ZONE_META[zone].label}</div>
                        {ZONE_META[zone].allowedBuildings.length > 0 ? (
                          ZONE_META[zone].allowedBuildings.map((b) => (
                            <div key={b} style={{ color: "var(--pt-muted)" }}>
                              {BUILDING_EMOJI[b]} {b.replace("_", " ")}
                            </div>
                          ))
                        ) : (
                          <div style={{ color: "var(--pt-muted)" }}>Koi building allowed nahi</div>
                        )}
                        {status === "zone" && (
                          <div style={{ color: "var(--pt-red-lt)" }}>
                            ❌ {selectedBuilding?.name} yahan nahi
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}

          {/* Legend */}
          <div className="mt-3 flex flex-wrap gap-2">
            {(Object.entries(ZONE_META) as [ZoneType, typeof ZONE_META[ZoneType]][]).map(([zoneId, meta]) => (
              <div key={zoneId} className="flex items-center gap-1 text-[9px]" style={{ color: "var(--pt-muted)" }}>
                <div className="h-2.5 w-2.5" style={{ background: meta.color, border: "1px solid rgba(255,255,255,0.15)" }} />
                {meta.label}
              </div>
            ))}
          </div>
          <div className="mt-1 text-[9px]" style={{ color: "var(--pt-muted)" }}>
            Left-click to build · Right-click to remove from map · Zone rules enforced
          </div>
        </div>

        {/* ── Sidebar: building picker + controls ────────────────────── */}
        <div className="flex flex-col gap-3">
          <div className="text-[10px] uppercase font-bold" style={{ color: "var(--pt-saffron)" }}>
            Building Chunein
          </div>

          {/* Building selector grid */}
          <div className="grid grid-cols-2 gap-1">
            {catalog.map((b) => (
              <button
                key={b.id}
                type="button"
                onClick={() => setSelectedBuilding(b)}
                className="flex flex-col items-center gap-0.5 p-2 text-[9px] font-bold transition-all"
                style={{
                  background: selectedBuilding?.id === b.id ? "var(--pt-saffron)" : "var(--pt-ink)",
                  border: `1px solid ${selectedBuilding?.id === b.id ? "var(--pt-saffron)" : "var(--pt-line)"}`,
                  color: selectedBuilding?.id === b.id ? "#fff" : "var(--pt-muted)",
                }}
              >
                <span className="text-lg">{BUILDING_EMOJI[b.id]}</span>
                <span className="text-center leading-tight">{b.name}</span>
                <span style={{ opacity: 0.7 }}>₹{(b.base_cost/1e5).toFixed(1)}L min</span>
              </button>
            ))}
          </div>

          {/* Selected building zone info */}
          {selectedBuilding && (
            <div className="p-2" style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)" }}>
              <div className="text-[9px] font-bold mb-1" style={{ color: "var(--pt-muted)" }}>
                VALID ZONES FOR {selectedBuilding.name.toUpperCase()}
              </div>
              <div className="flex flex-wrap gap-1">
                {(Object.entries(ZONE_META) as [ZoneType, typeof ZONE_META[ZoneType]][])
                  .filter(([, meta]) => meta.allowedBuildings.includes(selectedBuilding.id))
                  .map(([zoneId, meta]) => (
                    <div
                      key={zoneId}
                      className="px-1.5 py-0.5 text-[9px]"
                      style={{ background: meta.color, color: "rgba(255,255,255,0.8)" }}
                    >
                      {meta.label}
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Budget & siphon sliders */}
          <div className="p-2 grid gap-2" style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)" }}>
            <SliderRow
              label="Budget"     hindi="बजट"
              value={budget} min={100000} max={2000000} step={50000}
              onChange={setBudget} color="var(--pt-saffron)"
              fmt={(v) => `₹${(v/1e5).toFixed(1)}L`}
            />
            <SliderRow
              label="Corruption" hindi="भ्रष्टाचार"
              value={siphon} min={0} max={60} step={5}
              onChange={setSiphon} color="var(--pt-red)"
              fmt={(v) => `${v}%`}
            />
          </div>

          {/* Placed buildings list */}
          {mapState.placed.length > 0 && (
            <div className="p-2" style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)" }}>
              <div className="text-[9px] uppercase font-bold mb-1" style={{ color: "var(--pt-muted)" }}>
                Placed Buildings ({mapState.placed.length})
              </div>
              <div className="max-h-44 overflow-auto">
                {mapState.placed.map((p, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between py-0.5 text-[9px]"
                    style={{ borderBottom: "1px solid var(--pt-line)" }}
                  >
                    <span>{BUILDING_EMOJI[p.buildingId]} {p.name}</span>
                    <span style={{ color: "var(--pt-muted)" }}>
                      {p.row+1}{["A","B","C","D","E","F","G","H"][p.col]}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function HealthBar({ label, value, color, invert = false }: {
  label: string; value: number; color: string; invert?: boolean;
}) {
  const display = invert ? 100 - value : value;
  return (
    <div className="flex flex-col gap-0.5 min-w-[80px]">
      <div className="flex justify-between text-[9px]">
        <span style={{ color: "var(--pt-muted)" }}>{label}</span>
        <span className="font-bold" style={{ color }}>{display}</span>
      </div>
      <div className="h-1.5" style={{ background: "var(--pt-line)" }}>
        <div
          className="h-full transition-all duration-500"
          style={{ width: `${display}%`, background: color }}
        />
      </div>
    </div>
  );
}

function SliderRow({ label, hindi, value, min, max, step, onChange, color, fmt }: {
  label: string; hindi: string; value: number; min: number; max: number; step: number;
  onChange: (v: number) => void; color: string; fmt: (v: number) => string;
}) {
  return (
    <label className="grid gap-0.5">
      <span className="flex justify-between text-[9px]">
        <span style={{ color: "var(--pt-muted)" }}>{label} <span style={{ opacity: 0.6 }}>· {hindi}</span></span>
        <span className="font-bold" style={{ color }}>{fmt(value)}</span>
      </span>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1.5" style={{ accentColor: color }}
      />
    </label>
  );
}
