// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

import { cn } from "@/lib/cn";
import type { Trend } from "@/lib/format";

/** An indicator over the last sessions: a line, the last point marked in the trend's colour.
 * It stretches to its container's width. */
export function Sparkline({
  values,
  trend,
  className,
}: {
  values: (number | null)[];
  trend: Trend;
  className?: string;
}) {
  const known = values.flatMap((v, i) => (v === null ? [] : [{ i, v }]));
  if (known.length < 2) return null;
  const width = 100;
  const height = 24;
  const low = Math.min(...known.map((p) => p.v));
  const high = Math.max(...known.map((p) => p.v));
  const x = (i: number) => (i / Math.max(1, values.length - 1)) * (width - 6) + 3;
  const y = (v: number) =>
    high === low ? height / 2 : height - 3 - ((v - low) / (high - low)) * (height - 6);
  const last = known.at(-1);
  const dot =
    trend === "better" ? "fill-win" : trend === "worse" ? "fill-loss" : "fill-muted-foreground";
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      className={cn("block h-6 w-full overflow-visible", className)}
    >
      <polyline
        points={known.map((p) => `${x(p.i)},${y(p.v)}`).join(" ")}
        fill="none"
        className="stroke-muted-foreground"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
      {last && (
        <circle
          cx={x(last.i)}
          cy={y(last.v)}
          r="2.5"
          className={dot}
          vectorEffect="non-scaling-stroke"
        />
      )}
    </svg>
  );
}
