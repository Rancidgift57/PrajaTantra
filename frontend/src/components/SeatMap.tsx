"use client";

/**
 * SeatMap — Hemicycle seat-map chart, styled after the classic Wikipedia
 * "parliament diagram" (see reference screenshot: a semicircle of coloured
 * dots grouped by party, a big seat-count in the centre, "By party /
 * By alliance" toggle underneath).
 *
 * Seats are generated as concentric arcs (innermost row first) and then
 * flattened + sorted by angle so each party occupies a contiguous wedge,
 * left → right: Incumbent, Independents, Opposition.
 */

import { useMemo, useState } from "react";
import type { SeatResult } from "@/lib/api";

type ViewMode = "party" | "alliance";

type Seat = { x: number; y: number; angleDeg: number; color: string; party: string };

// Concentric-arc hemicycle layout, matching Wikipedia-style parliament charts.
// Positions are computed around a (0,0) pivot at the flat edge of the
// semicircle; the caller offsets them onto the final canvas.
function layoutHemicycle(total: number, innerRadius: number, dotR: number, gap: number) {
  const rowGap = dotR * 2 + gap;
  const dotSpacing = dotR * 2 + gap * 0.7;
  const rows: { radius: number; count: number }[] = [];
  let remaining = total;
  let radius = innerRadius;
  while (remaining > 0) {
    const circumference = Math.PI * radius;
    let seatsInRow = Math.max(1, Math.floor(circumference / dotSpacing));
    seatsInRow = Math.min(seatsInRow, remaining);
    rows.push({ radius, count: seatsInRow });
    remaining -= seatsInRow;
    radius += rowGap;
  }

  const positions: { x: number; y: number; angleDeg: number }[] = [];
  for (const row of rows) {
    for (let i = 0; i < row.count; i++) {
      const t = row.count === 1 ? 0.5 : i / (row.count - 1);
      const angleDeg = 180 - t * 180; // 180 (left) -> 0 (right)
      const angleRad = (angleDeg * Math.PI) / 180;
      positions.push({
        x: Math.cos(angleRad) * row.radius,
        y: -Math.sin(angleRad) * row.radius,
        angleDeg,
      });
    }
  }
  // Sort left -> right so contiguous colour blocks form clean wedges.
  positions.sort((a, b) => b.angleDeg - a.angleDeg);
  const outerRadius = radius - rowGap + dotR;
  return { positions, outerRadius };
}

export default function SeatMap({
  seats,
  totalSeats,
  incumbentName,
  oppositionName,
}: {
  seats: SeatResult[];
  totalSeats: number;
  incumbentName: string;
  oppositionName: string;
}) {
  const [mode, setMode] = useState<ViewMode>("party");

  const dotR = totalSeats > 140 ? 4.6 : totalSeats > 80 ? 5.6 : 7;
  const gap = 3.2;
  const innerRadius = 34;

  const { positions, outerRadius } = useMemo(
    () => layoutHemicycle(totalSeats, innerRadius, dotR, gap),
    [totalSeats, dotR, gap],
  );

  const PAD = 16;
  const cx = outerRadius + PAD;
  const cy = outerRadius + PAD;
  const W = cx * 2;
  const H = cy + dotR + 18;

  // Order groups left -> right: Incumbent, Independents, Opposition —
  // mirrors the reference chart (ruling bloc on the left, fringe seats in
  // the middle gap, main opposition on the right).
  const ordered = useMemo(() => {
    const inc = seats.find((s) => s.role === "Incumbent");
    const ind = seats.find((s) => s.role === "Independent");
    const opp = seats.find((s) => s.role === "Opposition");
    return [inc, ind, opp].filter(Boolean) as SeatResult[];
  }, [seats]);

  const dots: Seat[] = useMemo(() => {
    const flat: Seat[] = [];
    let cursor = 0;
    for (const group of ordered) {
      for (let i = 0; i < group.seats; i++) {
        const pos = positions[cursor];
        if (!pos) break;
        flat.push({ x: cx + pos.x, y: cy + pos.y, angleDeg: pos.angleDeg, color: group.color, party: group.party });
        cursor += 1;
      }
    }
    return flat;
  }, [ordered, positions, cx, cy]);

  return (
    <div className="mt-3 p-3" style={{ border: "1px solid var(--pt-line)", background: "var(--pt-ink)" }}>
      <div className="mb-1 flex items-center justify-between">
        <div className="text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>
          Seats — सीट मानचित्र
        </div>
        <div className="text-[10px] font-black" style={{ color: "var(--pt-white)" }}>{totalSeats}</div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block" }} aria-label="Election seat map">
        {dots.map((seat, i) => (
          <circle
            key={i}
            cx={seat.x}
            cy={seat.y}
            r={dotR}
            fill={mode === "party" ? seat.color : "var(--pt-panel-hi)"}
            stroke="rgba(0,0,0,0.35)"
            strokeWidth="0.6"
          />
        ))}
        {/* Total-seats readout, centred under the arc */}
        <text
          x={cx}
          y={cy - innerRadius * 0.15}
          textAnchor="middle"
          fontSize="22"
          fontWeight="900"
          fill="var(--pt-white)"
        >
          {totalSeats}
        </text>
      </svg>

      {/* Legend */}
      <div className="mt-1 flex flex-wrap items-center gap-3 text-[10px]">
        {ordered.map((s) => (
          <span key={s.party} className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
            <span style={{ color: "var(--pt-muted)" }}>
              {s.party === incumbentName || s.role === "Incumbent"
                ? incumbentName
                : s.party === oppositionName || s.role === "Opposition"
                ? oppositionName
                : s.party}
            </span>
            <span className="font-black" style={{ color: s.color }}>{s.seats}</span>
          </span>
        ))}
      </div>

      {/* By party / By alliance toggle — matches the reference chart chrome */}
      <div className="mt-2 flex flex-col gap-1 text-[11px]" style={{ color: "var(--pt-muted)" }}>
        {([
          ["party", "By party"],
          ["alliance", "By alliance"],
        ] as const).map(([value, label]) => (
          <label key={value} className="flex cursor-pointer items-center gap-2">
            <span
              className="flex h-3.5 w-3.5 items-center justify-center rounded-full"
              style={{ border: `1.5px solid ${mode === value ? "var(--pt-saffron)" : "var(--pt-line)"}` }}
            >
              {mode === value && (
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--pt-saffron)" }} />
              )}
            </span>
            <input
              type="radio"
              className="hidden"
              checked={mode === value}
              onChange={() => setMode(value)}
              name="seatmap-mode"
            />
            {label}
          </label>
        ))}
      </div>
    </div>
  );
}
