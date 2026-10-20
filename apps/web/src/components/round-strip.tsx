// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

export interface StripMark {
  tick: number;
  /** Accessible name of the round's button. */
  label: string;
  /** The sentence before the command: which round, which side, what to do in CS2. */
  command: string;
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
 * A match's rounds, the ones to review framed: filled = won, the bottom line = the side played.
 * Choosing a framed round shows its `demo_gototick` command, ready to copy.
 */
export function RoundStrip({
  title,
  legend,
  cells,
  labels,
}: {
  title: string;
  legend: string;
  cells: StripCell[];
  labels: { copy: string; copied: string };
}) {
  const marked = cells.filter((cell) => cell.mark);
  const [selected, setSelected] = useState(marked[0]?.round ?? 0);
  const [copied, setCopied] = useState(false);
  const current = marked.find((cell) => cell.round === selected) ?? marked[0];
  if (!current?.mark) return null;
  const command = `demo_gototick ${current.mark.tick}`;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap justify-between gap-x-4 gap-y-1 text-[0.8125rem] text-muted-foreground">
        <span>{title}</span>
        <span>{legend}</span>
      </div>
      <div
        className="grid gap-0.5 sm:gap-[3px]"
        style={{ gridTemplateColumns: `repeat(${cells.length}, minmax(0, 1fr))` }}
      >
        {cells.map((cell) => {
          const look = cn(
            "grid h-[22px] place-items-center rounded-[2px] border border-border text-[0.65rem] sm:h-[26px] sm:text-[0.6875rem]",
            cell.won && "bg-muted",
            cell.side === "CT" && "border-b-[3px] border-b-side-ct",
            cell.side === "T" && "border-b-[3px] border-b-side-t",
            cell.half && "ml-1 sm:ml-1.5",
          );
          if (!cell.mark) {
            return (
              <span
                key={cell.round}
                aria-hidden="true"
                className={cn(look, "text-transparent sm:text-muted-foreground")}
              >
                {cell.round}
              </span>
            );
          }
          const on = cell.round === current.round;
          return (
            <button
              key={cell.round}
              type="button"
              aria-pressed={on}
              aria-label={cell.mark.label}
              onClick={() => {
                setSelected(cell.round);
                setCopied(false);
              }}
              className={cn(
                look,
                "cursor-pointer font-semibold text-foreground shadow-[inset_0_0_0_2px_var(--foreground)]",
                on && "bg-foreground text-background",
              )}
            >
              {cell.round}
            </button>
          );
        })}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm">
        <span>{current.mark.command}</span>
        <span className="inline-flex h-8 max-w-full items-center gap-1 rounded-md border border-border bg-background pr-1 pl-2.5">
          <code translate="no" className="truncate font-mono text-[0.8125rem]">
            {command}
          </code>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={labels.copy}
            title={labels.copy}
            onClick={() => {
              navigator.clipboard.writeText(command).then(
                () => setCopied(true),
                () => setCopied(false),
              );
            }}
          >
            {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
          </Button>
        </span>
        <span aria-live="polite" className="sr-only">
          {copied ? labels.copied : ""}
        </span>
      </div>
    </div>
  );
}
