// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import type { Trend } from "@/lib/format";
import type { Geometry } from "@/lib/progress";

/** One session of the curve, already written out on the server. */
export interface ChartPoint {
  date: string;
  value: string;
  /** "ref. 1.02", or `null` without a reference that session. */
  reference: string | null;
  /** How the session compares to its reference, when it has one. */
  trend: Trend | null;
}

const ARROW: Record<Trend, string> = { better: "▲", worse: "▼", same: "=" };
const TONE: Record<Trend, string> = {
  better: "text-win",
  worse: "text-loss",
  same: "text-muted-foreground",
};

/**
 * A key figure's curve, drawn from a geometry computed on the server: the player's line, the
 * reference dashed, one point per session. Pointing at a session (mouse or touch) shows its date,
 * value and reference; the page lists the same values for screen readers and the keyboard.
 */
export function ProgressChart({
  geometry: g,
  points,
  ticks,
}: {
  geometry: Geometry;
  points: ChartPoint[];
  /** The value guides, written out (same order as `geometry.ticks`). */
  ticks: string[];
}) {
  const [active, setActive] = useState<number | null>(null);
  const band = active === null ? null : g.bands[active];
  const point = active === null ? null : points[active];
  const last = g.dots.length - 1;
  return (
    <div className="mt-1" onPointerLeave={() => setActive(null)}>
      {/* The session pointed at, on a line kept for it above the curve: a bubble over the chart
          covered the card's figures. Empty, it keeps its height, so the curve does not move. */}
      <p
        aria-hidden="true"
        className="flex h-5 items-baseline gap-1.5 text-xs whitespace-nowrap text-muted-foreground"
      >
        {point && (
          <>
            <span>{point.date}</span>
            <span className="text-[0.8125rem] font-semibold text-foreground tabular-nums">
              {point.value}
            </span>
            {point.reference && <span className="tabular-nums">{point.reference}</span>}
            {point.trend && <span className={cn(TONE[point.trend])}>{ARROW[point.trend]}</span>}
          </>
        )}
      </p>
      {/* Drawn for the eyes: the page gives the same values as a table to screen readers. */}
      <svg
        viewBox={`0 0 ${g.width} ${g.height}`}
        aria-hidden="true"
        className="block h-auto w-full overflow-visible"
      >
        {g.ticks.map((tick, i) => (
          <g key={tick.y}>
            <line x1={48} x2={g.width - 12} y1={tick.y} y2={tick.y} stroke="var(--line-soft)" />
            <text
              x={40}
              y={tick.y + 4}
              textAnchor="end"
              fontSize={11}
              fill="var(--muted-foreground)"
            >
              {ticks[i]}
            </text>
          </g>
        ))}
        {g.dates.map((date, i) =>
          // Two sessions on the same day: their date once.
          points[date.index]?.date === points[g.dates[i - 1]?.index ?? -1]?.date ? null : (
            <text
              key={date.index}
              x={date.x}
              y={g.height - 6}
              textAnchor="middle"
              fontSize={11}
              fill="var(--muted-foreground)"
            >
              {points[date.index]?.date}
            </text>
          ),
        )}
        {band && (
          <line
            x1={band.x + band.width / 2}
            x2={band.x + band.width / 2}
            y1={g.plot.top}
            y2={g.plot.bottom}
            stroke="var(--border)"
          />
        )}
        <path
          d={g.referenceLine}
          fill="none"
          stroke="var(--muted-foreground)"
          strokeWidth={1.5}
          strokeDasharray="5 4"
        />
        <path d={g.line} fill="none" stroke="var(--foreground)" strokeWidth={2} />
        {g.dots.map((dot, i) => (
          <circle
            key={`${dot.x}-${dot.y}`}
            cx={dot.x}
            cy={dot.y}
            r={i === last ? 4.5 : 3}
            fill={i === last ? "var(--foreground)" : "var(--card)"}
            stroke="var(--foreground)"
            strokeWidth={1.5}
          />
        ))}
        {g.bands.map((b, i) => (
          <rect
            key={b.x}
            x={b.x}
            y={g.plot.top}
            width={b.width}
            height={g.plot.bottom - g.plot.top}
            fill="transparent"
            onPointerEnter={() => setActive(i)}
            onPointerDown={() => setActive(i)}
          />
        ))}
      </svg>
    </div>
  );
}
