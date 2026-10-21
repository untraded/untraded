// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import type { GapKind, Trend } from "@/lib/format";

/** One metric, already formatted on the server. `gap` is oriented: positive = better. */
export interface GapRow {
  id: string;
  name: string;
  family: string;
  perRound: string | null;
  value: string;
  /** The reference, as displayed under the value ("ref. 75.6"). */
  reference: string;
  gap: number | null;
  /** How it compares: only `ranked` rows have a % gap and a bar (see `compare()`). */
  kind: GapKind;
  /** What a rate stands on, when it is little ("over 7 cases"); `null` otherwise. */
  cases: string | null;
  gapText: string;
  trend: Trend;
}

const ARROW: Record<Trend, string> = { better: "▲", worse: "▼", same: "=" };
const TONE: Record<Trend, string> = {
  better: "text-win",
  worse: "text-loss",
  same: "text-muted-foreground",
};

/**
 * Every metric of the session as its gap to the reference: a bar from the reference, to the right
 * when better whatever way the metric runs. First what stands out (the largest gaps both ways),
 * then one family at a time.
 */
export function MetricGaps({
  families,
  standout,
  labels,
}: {
  families: { key: string; label: string; rows: GapRow[] }[];
  /** `null` without a reference: there is nothing to rank. */
  standout: { worse: GapRow[]; better: GapRow[] } | null;
  labels: {
    standout: string;
    worseThan: string;
    betterThan: string;
    families: string;
    metric: string;
    session: string;
    delta: string;
    worse: string;
    better: string;
    neutral: string;
    noReference: string;
    rare: string;
    standoutEmpty: string;
  };
}) {
  const [shown, setShown] = useState(standout ? "standout" : (families[0]?.key ?? ""));
  const chip =
    "inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-card px-3 text-[0.8125rem] text-muted-foreground hover:text-foreground aria-pressed:border-highlight-soft aria-pressed:bg-highlight-soft aria-pressed:font-semibold aria-pressed:text-foreground";
  const family = families.find((f) => f.key === shown);
  return (
    <div className="flex flex-col gap-3">
      <fieldset className="m-0 flex flex-wrap gap-1.5 border-0 p-0">
        <legend className="sr-only">{labels.families}</legend>
        {standout && (
          <button
            type="button"
            className={chip}
            aria-pressed={shown === "standout"}
            onClick={() => setShown("standout")}
          >
            {labels.standout}
          </button>
        )}
        {families.map((f) => (
          <button
            key={f.key}
            type="button"
            className={chip}
            aria-pressed={shown === f.key}
            onClick={() => setShown(f.key)}
          >
            {f.label}
            <span className="text-xs opacity-80">{f.rows.length}</span>
          </button>
        ))}
      </fieldset>
      {shown === "standout" && standout ? (
        standout.worse.length + standout.better.length === 0 ? (
          <p className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
            {labels.standoutEmpty}
          </p>
        ) : (
          <>
            {standout.worse.length > 0 && (
              <Group title={labels.worseThan} rows={standout.worse} labels={labels} withFamily />
            )}
            {standout.better.length > 0 && (
              <Group title={labels.betterThan} rows={standout.better} labels={labels} withFamily />
            )}
          </>
        )
      ) : (
        family && <Group rows={family.rows} labels={labels} compare={standout !== null} />
      )}
    </div>
  );
}

function Group({
  title,
  rows,
  labels,
  withFamily = false,
  compare = true,
}: {
  title?: string;
  rows: GapRow[];
  labels: Parameters<typeof MetricGaps>[0]["labels"];
  withFamily?: boolean;
  compare?: boolean;
}) {
  const grid = compare
    ? "grid-cols-[minmax(0,1fr)_4rem] sm:grid-cols-[minmax(0,1.3fr)_5rem_minmax(7rem,1.4fr)_5rem]"
    : "grid-cols-[minmax(0,1fr)_5rem]";
  return (
    <div>
      {title && <h3 className="mt-2 mb-1 text-sm font-semibold">{title}</h3>}
      <div
        aria-hidden="true"
        className={cn("hidden gap-3.5 pb-1 text-xs text-muted-foreground sm:grid", grid)}
      >
        <span>{labels.metric}</span>
        <span className="text-right">{labels.session}</span>
        {compare && (
          <>
            <span className="flex justify-between">
              <span>◀ {labels.worse}</span>
              <span>{labels.better} ▶</span>
            </span>
            <span className="text-right">{labels.delta}</span>
          </>
        )}
      </div>
      <ul>
        {rows.map((row) => {
          const width = row.gap === null ? 0 : (Math.min(Math.abs(row.gap), 50) / 50) * 50;
          const note = [
            withFamily ? row.family : null,
            row.perRound,
            row.kind === "ranked" ? row.cases : null,
          ]
            .filter(Boolean)
            .join(", ");
          return (
            <li
              key={row.id}
              className={cn(
                "grid items-center gap-x-3.5 gap-y-1 border-t border-line-soft py-2 text-sm",
                grid,
              )}
            >
              <span>
                {row.name}
                {note && <span className="block text-xs text-muted-foreground">{note}</span>}
              </span>
              <span className={cn("text-right font-semibold", compare && "hidden sm:block")}>
                {row.value}
                {compare && (
                  <span className="block text-xs font-normal text-muted-foreground">
                    {row.reference}
                  </span>
                )}
              </span>
              {compare && (
                <>
                  <span
                    aria-hidden="true"
                    className="relative col-span-2 h-3.5 before:absolute before:inset-y-[-3px] before:left-1/2 before:w-px before:bg-border sm:col-span-1"
                  >
                    {row.gap !== null && (
                      <span
                        className={cn(
                          "absolute top-[3px] h-2 rounded-[2px]",
                          row.gap >= 0 ? "left-1/2 bg-win" : "right-1/2 bg-loss",
                        )}
                        style={{ width: `${width}%` }}
                      />
                    )}
                  </span>
                  <span
                    className={cn(
                      "col-start-2 row-start-1 text-right text-[0.8125rem] whitespace-nowrap sm:col-start-auto sm:row-start-auto",
                      TONE[row.trend],
                    )}
                  >
                    {row.kind === "neutral" ? (
                      labels.neutral
                    ) : row.kind === "few" ? (
                      row.cases
                    ) : row.kind === "rare" ? (
                      labels.rare
                    ) : row.kind === "none" ? (
                      labels.noReference
                    ) : (
                      <>
                        <span aria-hidden="true">{ARROW[row.trend]}</span> {row.gapText}
                      </>
                    )}
                  </span>
                </>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
