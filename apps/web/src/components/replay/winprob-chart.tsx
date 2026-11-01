// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { ExternalLink } from "lucide-react";
import { memo, type PointerEvent, useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import type { Replay, ReplayWinProb } from "@/lib/replay";
import {
  chanceAt,
  curve,
  events,
  keyMoments,
  marked,
  points,
  type WinProbEvent,
} from "@/lib/winprob";

export interface WinProbLabels {
  title: string;
  /** `{model}` is replaced. */
  model: string;
  method: string;
  legend: string;
  moments: string;
  /** `{attacker}` and `{victim}`. */
  kill: string;
  /** `{player}`. */
  plant: string;
  defuse: string;
  /** `{points}` and `{side}`. */
  forSide: string;
  /** `{what}` and `{time}`. */
  seek: string;
}

const fill = (template: string, values: Record<string, string>) =>
  template.replace(/\{(\w+)\}/g, (_, key: string) => values[key] ?? "");

/** The drawing's height, in px; its width follows the timeline above it. */
const HEIGHT = 96;

/** A tick's place along the drawing, in % of the round. */
const shareOf = (replay: Replay, t: number) =>
  Math.min(
    100,
    Math.max(0, ((t - replay.start_tick) / (replay.end_tick - replay.start_tick)) * 100),
  );

/** An action of the curve, said once: who did what, for which side, the credits, and the label
 * that moves the playback there. */
interface Described {
  event: WinProbEvent;
  key: string;
  /** The counter-terrorists' chance after it: where its mark stands. */
  p: number;
  what: string;
  gain: string;
  credits: string;
  time: string;
  seek: string;
}

function describe(
  event: WinProbEvent,
  replay: Replay,
  winprob: ReplayWinProb,
  name: (steamid: string) => string,
  roundTime: (tick: number) => string,
  labels: WinProbLabels,
): Described {
  let what: string;
  if (event.event !== "kill") {
    const player = name(event.credits[0]?.player ?? "");
    what = fill(event.event === "plant" ? labels.plant : labels.defuse, { player });
  } else {
    const victim = event.credits.find((c) => c.swing < 0);
    const kill =
      replay.kills.find((k) => k.tick === event.tick && k.victim === victim?.player) ??
      replay.kills.find((k) => k.tick === event.tick);
    what = fill(labels.kill, {
      attacker: kill?.attacker ? name(kill.attacker) : "?",
      victim: kill ? name(kill.victim) : "?",
    });
  }
  const gain = fill(labels.forSide, { points: points(Math.abs(event.ct)), side: event.gainer });
  const time = roundTime(event.tick);
  return {
    event,
    key: `${event.tick}-${event.event}`,
    p: chanceAt(winprob, event.tick),
    what,
    gain,
    credits: event.credits
      .filter((c) => Math.abs(c.swing) >= 0.005)
      .map((c) => `${name(c.player)} ${points(c.swing)}`)
      .join(" · "),
    time,
    seek: fill(labels.seek, { what: `${what}, ${gain}`, time }),
  };
}

interface StaticProps {
  replay: Replay;
  winprob: ReplayWinProb;
  onSeek: (tick: number) => void;
  roundTime: (tick: number) => string;
  name: (steamid: string) => string;
  labels: WinProbLabels;
}

/** The curve itself, under the cursor: it does not move with the playback. */
const Curve = memo(function Curve({ replay, winprob }: { replay: Replay; winprob: ReplayWinProb }) {
  // The curve in a 100 × 100 box stretched to the timeline's width: x in % of the round.
  const path = useMemo(() => {
    const line = curve(replay, winprob)
      .map(
        (p, i) =>
          `${i ? "L" : "M"}${shareOf(replay, p.tick).toFixed(2)} ${(100 - p.p * 100).toFixed(2)}`,
      )
      .join(" ");
    return { line, area: `${line} L100 100 L0 100 Z` };
  }, [replay, winprob]);
  const freeze = shareOf(replay, replay.freeze_end_tick);
  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      aria-hidden="true"
      className="absolute inset-0 size-full overflow-visible rounded-sm"
    >
      <rect width="100" height="100" fill="var(--t)" opacity="0.22" />
      <path d={path.area} fill="var(--ct)" opacity="0.3" />
      <line
        x1="0"
        x2="100"
        y1="50"
        y2="50"
        stroke="var(--border)"
        strokeDasharray="4 3"
        vectorEffect="non-scaling-stroke"
      />
      <line
        x1={freeze}
        x2={freeze}
        y1="0"
        y2="100"
        stroke="var(--border)"
        vectorEffect="non-scaling-stroke"
      />
      <path
        d={path.line}
        fill="none"
        stroke="var(--foreground)"
        strokeWidth="1.75"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
});

/** The actions marked on the curve, with who did what on hover or focus. */
const Marks = memo(function Marks({ marks, ...props }: StaticProps & { marks: WinProbEvent[] }) {
  const { replay, winprob, onSeek, roundTime, name, labels } = props;
  const [shown, setShown] = useState<Described | null>(null);
  const items = useMemo(
    () => marks.map((event) => describe(event, replay, winprob, name, roundTime, labels)),
    [marks, replay, winprob, name, roundTime, labels],
  );
  return (
    <>
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          aria-label={item.seek}
          onPointerEnter={() => setShown(item)}
          onPointerLeave={() => setShown(null)}
          onFocus={() => setShown(item)}
          onBlur={() => setShown(null)}
          onClick={() => onSeek(item.event.tick - 3 * replay.tickrate)}
          className={cn(
            "absolute -translate-1/2 cursor-pointer border-2 bg-card outline-offset-2 focus-visible:outline-2 focus-visible:outline-ring",
            item.event.event === "kill" ? "rounded-full" : "size-2.5 rotate-45 rounded-[1px]",
            item.event.gainer === "CT" ? "border-side-ct" : "border-side-t",
          )}
          style={{
            left: `${shareOf(replay, item.event.tick)}%`,
            top: `${(1 - item.p) * HEIGHT}px`,
            ...(item.event.event === "kill"
              ? {
                  width: 8 + Math.abs(item.event.ct) * 14,
                  height: 8 + Math.abs(item.event.ct) * 14,
                }
              : {}),
          }}
        />
      ))}
      {shown && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-md border border-border bg-background px-2 py-1.5 text-xs whitespace-nowrap shadow-sm"
          style={{
            left: `clamp(7rem, ${shareOf(replay, shown.event.tick)}%, calc(100% - 7rem))`,
            top: `${(1 - shown.p) * HEIGHT - 10}px`,
          }}
        >
          <div>
            <span className="font-semibold">{shown.what}</span>{" "}
            <span className="font-mono text-muted-foreground">{shown.time}</span>
          </div>
          <div className={shown.event.gainer === "CT" ? "text-side-ct" : "text-side-t"}>
            {shown.gain}
          </div>
          <div className="text-muted-foreground">{shown.credits}</div>
        </div>
      )}
    </>
  );
});

/** The heaviest actions, listed under the curve; each one moves the playback there. */
const Moments = memo(function Moments({
  moments,
  ...props
}: StaticProps & { moments: WinProbEvent[] }) {
  const { replay, winprob, onSeek, roundTime, name, labels } = props;
  const items = useMemo(
    () => moments.map((event) => describe(event, replay, winprob, name, roundTime, labels)),
    [moments, replay, winprob, name, roundTime, labels],
  );
  if (items.length === 0) return null;
  return (
    <section className="mt-1 flex flex-col gap-1">
      <h3 className="text-xs font-medium text-muted-foreground">{labels.moments}</h3>
      <ol className="flex flex-col rounded-md border border-border">
        {items.map((item) => (
          <li key={item.key} className="border-t border-line-soft first:border-t-0">
            <button
              type="button"
              onClick={() => onSeek(item.event.tick - 3 * replay.tickrate)}
              aria-label={item.seek}
              className="grid w-full cursor-pointer grid-cols-[2.75rem_minmax(0,1fr)_auto] items-baseline gap-x-2.5 px-2.5 py-1.5 text-left text-[0.8125rem] hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
            >
              <time className="font-mono text-xs text-muted-foreground">{item.time}</time>
              <span className="min-w-0">
                <span className="font-semibold">{item.what}</span>{" "}
                <span className="text-xs text-muted-foreground">{item.credits}</span>
              </span>
              <span
                className={cn(
                  "text-xs font-semibold whitespace-nowrap tabular-nums",
                  item.event.gainer === "CT" ? "text-side-ct" : "text-side-t",
                )}
              >
                {item.gain}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
});

/**
 * The round's win probability under the timeline, at the same scale: the counter-terrorists'
 * chance in blue from the bottom, the terrorists' in orange from the top, the playback cursor on
 * it. The actions that moved it most are marked on the curve, in the colour of the side they
 * helped, with who did what on hover or focus; the three heaviest are listed below, and each one
 * moves the playback there. Only the chance and the cursor follow the playback: the curve, its
 * marks and the list are rendered again only when the round changes.
 */
export function WinProbChart({
  replay,
  winprob,
  tick,
  onSeek,
  roundTime,
  name,
  labels,
  method,
}: StaticProps & {
  tick: number;
  /** Where the model is explained. */
  method: string;
}) {
  const list = useMemo(() => events(winprob), [winprob]);
  const marks = useMemo(() => marked(list), [list]);
  const moments = useMemo(() => keyMoments(list), [list]);
  const ct = chanceAt(winprob, tick);
  const at = shareOf(replay, tick);
  const pct = (value: number) => `${Math.round(value * 100)} %`;
  const fixed = { replay, winprob, onSeek, roundTime, name, labels };

  function onTrack(event: PointerEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest("button")) return;
    const box = event.currentTarget.getBoundingClientRect();
    onSeek(
      replay.start_tick +
        Math.min(1, Math.max(0, (event.clientX - box.left) / box.width)) *
          (replay.end_tick - replay.start_tick),
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 text-[0.8125rem]">
        <span className="font-semibold tabular-nums">
          <span className="text-side-ct">CT {pct(ct)}</span>
          {" · "}
          <span className="text-side-t">T {pct(1 - ct)}</span>
        </span>
        <span className="text-xs text-muted-foreground">
          {labels.title} · {fill(labels.model, { model: winprob.model })}
        </span>
      </div>
      {/* Pointing at the drawing moves the playback there, like the timeline. */}
      <div
        className="relative cursor-pointer touch-none"
        style={{ height: HEIGHT }}
        onPointerDown={onTrack}
      >
        <Curve replay={replay} winprob={winprob} />
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden="true"
          className="absolute inset-0 size-full overflow-visible"
        >
          <line
            x1={at}
            x2={at}
            y1="0"
            y2="100"
            stroke="var(--foreground)"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        <span
          aria-hidden="true"
          className="absolute top-1 left-1 text-[0.625rem] font-semibold text-side-t"
        >
          T
        </span>
        <span
          aria-hidden="true"
          className="absolute bottom-1 left-1 text-[0.625rem] font-semibold text-side-ct"
        >
          CT
        </span>
        <span
          aria-hidden="true"
          className="absolute size-2 -translate-1/2 rounded-full bg-foreground"
          style={{ left: `${at}%`, top: `${(1 - ct) * HEIGHT}px` }}
        />
        <Marks marks={marks} {...fixed} />
      </div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span>{labels.legend}</span>
        <a
          href={method}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-link underline underline-offset-3"
        >
          {labels.method}
          <ExternalLink aria-hidden="true" className="size-3" />
        </a>
      </div>
      <Moments moments={moments} {...fixed} />
    </div>
  );
}
