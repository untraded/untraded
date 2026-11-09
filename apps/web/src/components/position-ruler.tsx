// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { cn } from "@/lib/cn";
import type { Position } from "@/lib/position";

const DOT: Record<"better" | "worse" | "same", string> = {
  better: "bg-win shadow-[0_0_0_1px_var(--win)]",
  worse: "bg-loss shadow-[0_0_0_1px_var(--loss)]",
  same: "bg-foreground shadow-[0_0_0_1px_var(--foreground)]",
};

/**
 * One metric on its graduated ruler: the grey band holds the reference's common values (10th to
 * 90th percentile), the tick is its median, the dot is the session. The axis always runs towards
 * better on the right. Drawn with no script; the colour only doubles what the word and the sign
 * next to it say, and `label` carries all of it for screen readers.
 */
export function PositionRuler({
  position,
  tone,
  label,
}: {
  position: Position;
  tone: "better" | "worse" | "same";
  label: string;
}) {
  return (
    <div role="img" aria-label={label} className="relative mx-2 h-7">
      <span aria-hidden="true" className="absolute inset-x-0 top-[13px] h-0.5 bg-line-soft" />
      <span
        aria-hidden="true"
        className="absolute top-[9px] h-2.5 rounded-[2px] bg-border"
        style={{
          left: `${position.bandFrom}%`,
          width: `${position.bandTo - position.bandFrom}%`,
        }}
      />
      <span
        aria-hidden="true"
        className="absolute top-[5px] -ml-px h-[18px] w-0.5 bg-muted-foreground"
        style={{ left: `${position.median}%` }}
      />
      <span
        aria-hidden="true"
        className={cn(
          "absolute top-[7px] -ml-[7px] size-3.5 rounded-full border-2 border-card",
          DOT[tone],
        )}
        style={{ left: `${position.at}%` }}
      />
    </div>
  );
}

/** What the ruler's three marks mean, as a closed-by-default note under the section's title. */
export function RulerLegend({
  title,
  dot,
  median,
  band,
  note,
}: {
  title: string;
  dot: string;
  median: string;
  band: string;
  note: string;
}) {
  return (
    <details className="max-w-[78ch] text-sm text-muted-foreground">
      <summary className="w-fit cursor-pointer rounded-sm py-1 underline decoration-dotted underline-offset-4 hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
        {title}
      </summary>
      <div className="mt-2 flex flex-col gap-2 rounded-lg border border-border bg-card px-3.5 py-3">
        <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs">
          <li className="flex items-center gap-1.5">
            <span aria-hidden="true" className="size-2.5 rounded-full bg-foreground" />
            {dot}
          </li>
          <li className="flex items-center gap-1.5">
            <span aria-hidden="true" className="h-3 w-0.5 bg-muted-foreground" />
            {median}
          </li>
          <li className="flex items-center gap-1.5">
            <span aria-hidden="true" className="h-2 w-[18px] rounded-[2px] bg-border" />
            {band}
          </li>
        </ul>
        <p>{note}</p>
      </div>
    </details>
  );
}
