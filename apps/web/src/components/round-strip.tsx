// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Check, Copy, Map as MapIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/cn";

export interface StripMark {
  /** Accessible name of the round's button. */
  label: string;
  /** The sentence before the commands: which round, which side, what to do in CS2. */
  command: string;
  /** Every moment to review in the round (a rule can flag several), in the order they happened. */
  moments: { tick: number; label: string; copy: string; view?: string }[];
}

export interface StripCell {
  round: number;
  won: boolean | null;
  side: "CT" | "T" | null;
  /** First round of a half: a gap before it. */
  half: boolean;
  mark?: StripMark;
}

/**
 * A match's rounds, the ones to review framed: filled = won, the bottom line = the side played,
 * also written above each half. Choosing a framed round shows the `demo_gototick` command of each
 * of its moments, ready to copy.
 */
export function RoundStrip({
  title,
  legend,
  cells,
  labels,
  match = true,
}: {
  title: string;
  legend: string;
  cells: StripCell[];
  /** `false` when the match could not be loaded: only its rounds to review, not consecutive. */
  match?: boolean;
  labels: { copied: string; view: string };
}) {
  const marked = cells.filter((cell) => cell.mark);
  const [selected, setSelected] = useState(marked[0]?.round ?? 0);
  const [copied, setCopied] = useState<number | null>(null);
  const current = marked.find((cell) => cell.round === selected) ?? marked[0];
  if (!current?.mark) return null;

  // Consecutive rounds played on the same side: the halves (and overtime halves).
  const halves: StripCell[][] = [];
  for (const cell of cells) {
    const last = halves.at(-1);
    if (last && !cell.half && last[0]?.side === cell.side) last.push(cell);
    else halves.push([cell]);
  }
  const widest = Math.max(...halves.map((h) => h.length));
  const sides = halves.some((h) => h[0]?.side);

  const cell = (c: StripCell, phone: boolean) => {
    const look = cn(
      "grid h-[26px] place-items-center rounded-[2px] border border-border text-[0.6875rem]",
      c.won && "bg-muted",
      c.side === "CT" && "border-b-[3px] border-b-side-ct",
      c.side === "T" && "border-b-[3px] border-b-side-t",
      !phone && c.half && "ml-1.5",
    );
    if (!c.mark) {
      return (
        <span key={c.round} aria-hidden="true" className={cn(look, "text-muted-foreground")}>
          {c.round}
        </span>
      );
    }
    const on = c.round === current.round;
    return (
      <button
        key={c.round}
        type="button"
        aria-pressed={on}
        aria-label={c.mark.label}
        onClick={() => {
          setSelected(c.round);
          setCopied(null);
        }}
        className={cn(
          look,
          "cursor-pointer font-semibold text-foreground shadow-[inset_0_0_0_2px_var(--foreground)]",
          on && "bg-foreground text-background",
        )}
      >
        {c.round}
      </button>
    );
  };

  function commands() {
    if (!current?.mark) return null;
    const mark = current.mark;
    return (
      <div className="flex flex-col gap-1.5 text-sm">
        <span>{mark.command}</span>
        <ul className="flex flex-col gap-1.5">
          {mark.moments.map((moment) => {
            const command = `demo_gototick ${moment.tick}`;
            return (
              <li key={moment.tick} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                {mark.moments.length > 1 && (
                  <span className="text-[0.8125rem] text-muted-foreground">{moment.label}</span>
                )}
                <span className="inline-flex h-8 max-w-full items-center gap-1 rounded-md border border-border bg-background pr-1 pl-2.5">
                  <code translate="no" className="truncate font-mono text-[0.8125rem]">
                    {command}
                  </code>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={moment.copy}
                    title={moment.copy}
                    onClick={() => {
                      navigator.clipboard.writeText(command).then(
                        () => setCopied(moment.tick),
                        () => setCopied(null),
                      );
                    }}
                  >
                    {copied === moment.tick ? (
                      <Check aria-hidden="true" />
                    ) : (
                      <Copy aria-hidden="true" />
                    )}
                  </Button>
                </span>
                {moment.view && (
                  <Link
                    href={moment.view}
                    className={cn(buttonVariants({ variant: "outline", size: "sm" }), "gap-1.5")}
                  >
                    <MapIcon aria-hidden="true" />
                    {labels.view}
                  </Link>
                )}
              </li>
            );
          })}
        </ul>
        <span aria-live="polite" className="sr-only">
          {copied === null ? "" : labels.copied}
        </span>
      </div>
    );
  }

  const panel = commands();
  if (!match) {
    // Rounds that do not follow each other: fixed cells, the side written in each one.
    return (
      <div className="flex flex-col gap-2">
        <span className="text-[0.8125rem] text-muted-foreground">{title}</span>
        <div className="flex flex-wrap gap-1">
          {cells.map((c) => (
            <button
              key={c.round}
              type="button"
              aria-pressed={c.round === current.round}
              aria-label={c.mark?.label}
              onClick={() => {
                setSelected(c.round);
                setCopied(null);
              }}
              className={cn(
                "flex h-10 w-11 cursor-pointer flex-col items-center justify-center rounded-[2px] border border-border text-xs leading-tight font-semibold shadow-[inset_0_0_0_2px_var(--foreground)]",
                c.side === "CT" && "border-b-[3px] border-b-side-ct",
                c.side === "T" && "border-b-[3px] border-b-side-t",
                c.round === current.round && "bg-foreground text-background",
              )}
            >
              {c.round}
              <span className="text-[0.625rem] font-normal">{c.side}</span>
            </button>
          ))}
        </div>
        {panel}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap justify-between gap-x-4 gap-y-1 text-[0.8125rem] text-muted-foreground">
        <span>{title}</span>
        <span>{legend}</span>
      </div>
      {/* Phone: one row per half, the side written above it, so the rounds stay readable even
          with 24 rounds and overtime. */}
      <div className="flex flex-col gap-1.5 sm:hidden">
        {halves.map((half) => (
          <div key={half[0]?.round} className="flex flex-col gap-0.5">
            {sides && (
              <span
                aria-hidden="true"
                className="text-[0.6875rem] font-semibold text-muted-foreground"
              >
                {half[0]?.side}
              </span>
            )}
            <div
              className="grid gap-0.5"
              style={{ gridTemplateColumns: `repeat(${widest}, minmax(0, 1fr))` }}
            >
              {half.map((c) => cell(c, true))}
            </div>
          </div>
        ))}
      </div>
      {/* Wider screens: the whole match on one row, the side written above each half. */}
      <div className="hidden flex-col gap-1 sm:flex">
        {sides && (
          <div
            aria-hidden="true"
            className="grid gap-[3px]"
            style={{ gridTemplateColumns: `repeat(${cells.length}, minmax(0, 1fr))` }}
          >
            {halves.map((half, i) => (
              <span
                key={half[0]?.round}
                style={{ gridColumn: `span ${half.length}` }}
                className={cn(
                  "border-l border-border pl-1 text-[0.6875rem] font-semibold text-muted-foreground",
                  i > 0 && "ml-1.5",
                )}
              >
                {half[0]?.side}
              </span>
            ))}
          </div>
        )}
        <div
          className="grid gap-[3px]"
          style={{ gridTemplateColumns: `repeat(${cells.length}, minmax(0, 1fr))` }}
        >
          {cells.map((c) => cell(c, false))}
        </div>
      </div>
      {panel}
    </div>
  );
}
