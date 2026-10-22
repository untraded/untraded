// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Pause, Play, RotateCcw, RotateCw } from "lucide-react";
import { type KeyboardEvent, type PointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { PUBLIC_API_PATH } from "@/lib/api-path";
import { cn } from "@/lib/cn";
import {
  clock,
  clockText,
  hasLevels,
  killWeapon,
  type Level,
  levelAt,
  nearest,
  REPLAY_VERSION,
  type Replay,
  sampleAt,
  startTick,
  weaponKind,
} from "@/lib/replay";
import type { Scene, SceneColors } from "./scene";

export interface ViewerLabels {
  canvas: string;
  loading: string;
  missing: string;
  failed: string;
  noGraphics: string;
  play: string;
  pause: string;
  back: string;
  forward: string;
  speed: string;
  timeline: string;
  level: string;
  upper: string;
  lower: string;
  freeze: string;
  bomb: string;
  noRadar: string;
  alive: string;
  dead: string;
  kills: string;
  noKills: string;
  headshot: string;
  world: string;
  knife: string;
  c4: string;
  keys: string;
  legendKill: string;
  legendBomb: string;
  legendFocus: string;
  markPlant: string;
  markFocus: string;
  /** `{attacker}`, `{victim}` and `{time}` are replaced by the viewer. */
  markKill: string;
}

const SPEEDS = [0.5, 1, 2, 4] as const;
/** How often the panel (teams, feed, clock) follows the playback, in ms. */
const PANEL_EVERY = 100;

/** The theme's colours, resolved by the browser (the tokens are `light-dark()` pairs). */
function readColors(probe: HTMLElement): SceneColors {
  const read = (token: string) => {
    probe.style.color = `var(${token})`;
    return getComputedStyle(probe).color;
  };
  return {
    radar: read("--foreground"),
    foreground: read("--foreground"),
    muted: read("--muted-foreground"),
    card: read("--card"),
    ct: read("--ct"),
    t: read("--t"),
    highlight: read("--highlight"),
    loss: read("--loss"),
  };
}

/** Moves the timeline's head while playing, without a React render each frame. */
function placeHead(
  replay: Replay,
  tick: number,
  head: HTMLElement | null,
  done: HTMLElement | null,
) {
  const share = ((tick - replay.start_tick) / (replay.end_tick - replay.start_tick)) * 100;
  if (head) head.style.left = `${share}%`;
  if (done) done.style.width = `${share}%`;
}

const fill = (template: string, values: Record<string, string>) =>
  template.replace(/\{(\w+)\}/g, (_, key: string) => values[key] ?? "");

/**
 * Replays a round from above: the radar, the players, grenades and bomb, with a timeline, speeds,
 * levels, the teams and the kill feed. Opens on `start` (a tick) with `focus` highlighted.
 */
export function ReplayViewer({
  matchId,
  round,
  start,
  focus,
  labels,
  locale,
}: {
  matchId: string;
  round: number;
  start: number | null;
  focus: string | null;
  labels: ViewerLabels;
  locale: string;
}) {
  const [replay, setReplay] = useState<Replay | null>(null);
  const [problem, setProblem] = useState<"missing" | "failed" | "noGraphics" | null>(null);
  const [tick, setTick] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);
  const [chosenLevel, setChosenLevel] = useState<Level | null>(null);
  const host = useRef<HTMLDivElement>(null);
  const probe = useRef<HTMLSpanElement>(null);
  const scene = useRef<Scene | null>(null);
  const tickRef = useRef(0);
  const playRef = useRef({ playing: false, speed: 1 as number });
  const viewRef = useRef<{ focus: string | null; level: Level }>({ focus, level: "upper" });
  const headRef = useRef<HTMLSpanElement>(null);
  const doneRef = useRef<HTMLSpanElement>(null);

  // The replay, from the API (gzipped, and cached by the browser: it never changes).
  useEffect(() => {
    let live = true;
    setReplay(null);
    setProblem(null);
    fetch(`${PUBLIC_API_PATH}/matches/${encodeURIComponent(matchId)}/rounds/${round}/replay`)
      .then(async (response) => {
        if (!live) return;
        if (response.status === 404) return setProblem("missing");
        if (!response.ok) return setProblem("failed");
        const data = (await response.json()) as Replay;
        if (!live) return;
        if (data.version !== REPLAY_VERSION) return setProblem("failed");
        const first = startTick(data, start);
        tickRef.current = first;
        setTick(first);
        setReplay(data);
      })
      .catch(() => live && setProblem("failed"));
    return () => {
      live = false;
    };
  }, [matchId, round, start]);

  // The level shown: the one chosen, else the highlighted player's.
  const sample = replay ? sampleAt(replay.ticks, tick) : null;
  const autoLevel: Level = replay ? levelAt(replay, focus, tick) : "upper";
  const level = chosenLevel ?? autoLevel;
  viewRef.current = { focus, level };
  playRef.current = { playing, speed };

  // The scene, and the clock that moves it while playing.
  useEffect(() => {
    if (!replay || !host.current || !probe.current) return;
    let live = true;
    let frame = 0;
    let last: number | null = null;
    let shown = 0;
    const box = host.current;
    const colors = readColors(probe.current);
    const draw = () => scene.current?.draw({ tick: tickRef.current, ...viewRef.current });
    import("./scene")
      .then(({ createScene }) => createScene(box, replay, box.clientWidth || 600, colors))
      .then((made) => {
        if (!live) return made.destroy();
        scene.current = made;
        draw();
        const loop = (now: number) => {
          if (!live) return;
          if (playRef.current.playing && last !== null) {
            const next =
              tickRef.current + ((now - last) / 1000) * replay.tickrate * playRef.current.speed;
            tickRef.current = Math.min(replay.end_tick, next);
            if (tickRef.current >= replay.end_tick) setPlaying(false);
            placeHead(replay, tickRef.current, headRef.current, doneRef.current);
            if (now - shown > PANEL_EVERY) {
              shown = now;
              setTick(tickRef.current);
            }
          }
          last = now;
          draw();
          frame = requestAnimationFrame(loop);
        };
        frame = requestAnimationFrame(loop);
      })
      .catch(() => live && setProblem("noGraphics"));
    const resize = new ResizeObserver(() => {
      scene.current?.resize(box.clientWidth);
      draw();
    });
    resize.observe(box);
    // A theme change (the user's choice or the system's): new colours.
    const recolor = () => {
      if (probe.current) scene.current?.setColors(readColors(probe.current));
      draw();
    };
    const themes = new MutationObserver(recolor);
    themes.observe(document.documentElement, { attributes: true });
    const dark = window.matchMedia("(prefers-color-scheme: dark)");
    dark.addEventListener("change", recolor);
    return () => {
      live = false;
      cancelAnimationFrame(frame);
      resize.disconnect();
      themes.disconnect();
      dark.removeEventListener("change", recolor);
      scene.current?.destroy();
      scene.current = null;
    };
  }, [replay]);

  function seek(next: number) {
    if (!replay) return;
    tickRef.current = Math.min(replay.end_tick, Math.max(replay.start_tick, next));
    setTick(tickRef.current);
    placeHead(replay, tickRef.current, headRef.current, doneRef.current);
  }

  function toggle() {
    if (!replay) return;
    if (!playing && tickRef.current >= replay.end_tick) seek(replay.start_tick);
    setPlaying(!playing);
  }

  // Positions of the timeline and its marks, in % of the round.
  const share = (t: number) =>
    // Within the round: an event can come after its last tick (a bomb planted as it ends).
    replay
      ? Math.min(
          100,
          Math.max(0, ((t - replay.start_tick) / (replay.end_tick - replay.start_tick)) * 100),
        )
      : 0;
  const byId = useMemo(() => new Map(replay?.players.map((p) => [p.steamid, p]) ?? []), [replay]);
  const focusTick = replay && start !== null ? start + 5 * replay.tickrate : null;

  if (problem) {
    return (
      <p role="alert" className="rounded-lg border border-border bg-card px-4 py-3 text-sm">
        {labels[problem]}
      </p>
    );
  }

  const roundTime = (t: number) => (replay ? clockText(clock(replay, t).seconds) : "");
  const now = replay ? clock(replay, tick) : null;
  const weapon = (index: number | null) => {
    const name = index === null ? null : (replay?.weapons[index] ?? null);
    const kind = weaponKind(name);
    return kind === "knife" ? labels.knife : kind === "c4" ? labels.c4 : (name ?? "–");
  };
  const name = (steamid: string | null) =>
    steamid === null ? labels.world : (byId.get(steamid)?.name ?? "?");
  const sideClass = (steamid: string | null) =>
    byId.get(steamid ?? "")?.side === "CT" ? "text-side-ct" : "text-side-t";

  function onKey(event: KeyboardEvent) {
    if (!replay) return;
    const step = (event.shiftKey ? 5 : 1) * replay.tickrate;
    if (event.key === " " || event.key === "k") {
      event.preventDefault();
      toggle();
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      seek(tickRef.current + step);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      seek(tickRef.current - step);
    }
  }

  function onTrack(event: PointerEvent<HTMLDivElement>) {
    if (!replay) return;
    const box = event.currentTarget.getBoundingClientRect();
    const share = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width));
    seek(replay.start_tick + share * (replay.end_tick - replay.start_tick));
  }

  return (
    // On a computer the map is as tall as the window allows, so the controls stay in view.
    <div className="grid gap-3.5 lg:grid-cols-[minmax(0,calc(100dvh-12rem))_18.5rem] lg:items-start">
      <span ref={probe} aria-hidden="true" className="hidden" />
      <section
        aria-label={labels.canvas}
        onKeyDown={onKey}
        className="overflow-hidden rounded-lg border border-border bg-card"
      >
        <div className="relative aspect-square w-full bg-muted">
          <div ref={host} className="absolute inset-0" role="img" aria-label={labels.canvas} />
          {!replay && (
            <p className="absolute inset-0 grid place-items-center text-sm text-muted-foreground">
              {labels.loading}
            </p>
          )}
          {replay && now && (
            <p
              aria-live="off"
              className={cn(
                "absolute top-2.5 left-2.5 rounded-md border border-border bg-card px-2.5 py-0.5 font-mono text-sm font-semibold tabular-nums",
                now.kind === "bomb" && "text-loss",
              )}
            >
              {clockText(now.seconds)}
              {now.kind !== "round" && (
                <span className="ml-1.5 font-sans text-xs font-medium text-muted-foreground">
                  {now.kind === "bomb" ? labels.bomb : labels.freeze}
                </span>
              )}
            </p>
          )}
          {replay && hasLevels(replay) && (
            <fieldset className="absolute top-2.5 right-2.5 m-0 inline-flex rounded-md border border-border bg-card p-0.5">
              <legend className="sr-only">{labels.level}</legend>
              {(["upper", "lower"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={level === value}
                  onClick={() => setChosenLevel(value)}
                  className="h-6 rounded-sm px-2.5 text-xs text-muted-foreground aria-pressed:bg-highlight-soft aria-pressed:font-semibold aria-pressed:text-foreground"
                >
                  {labels[value]}
                </button>
              ))}
            </fieldset>
          )}
          {replay && !replay.radar && (
            <p className="absolute bottom-2 left-2.5 text-xs text-muted-foreground">
              {labels.noRadar}
            </p>
          )}
        </div>
        {replay && (
          <>
            <div className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3.5 gap-y-2 border-t border-border px-3 py-2.5 sm:grid-cols-[auto_minmax(0,1fr)_auto]">
              <div className="flex items-center gap-1.5">
                <Button
                  variant="outline"
                  size="icon-sm"
                  aria-label={labels.back}
                  title={labels.back}
                  onClick={() => seek(tickRef.current - 5 * replay.tickrate)}
                >
                  <RotateCcw aria-hidden="true" />
                </Button>
                <Button
                  size="icon-sm"
                  aria-label={playing ? labels.pause : labels.play}
                  title={playing ? labels.pause : labels.play}
                  onClick={toggle}
                >
                  {playing ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
                </Button>
                <Button
                  variant="outline"
                  size="icon-sm"
                  aria-label={labels.forward}
                  title={labels.forward}
                  onClick={() => seek(tickRef.current + 5 * replay.tickrate)}
                >
                  <RotateCw aria-hidden="true" />
                </Button>
              </div>
              <div
                role="slider"
                tabIndex={0}
                aria-label={labels.timeline}
                aria-valuemin={replay.start_tick}
                aria-valuemax={replay.end_tick}
                aria-valuenow={Math.round(tick)}
                aria-valuetext={roundTime(tick)}
                onPointerDown={(event) => {
                  event.currentTarget.setPointerCapture(event.pointerId);
                  onTrack(event);
                }}
                onPointerMove={(event) => {
                  if (event.currentTarget.hasPointerCapture(event.pointerId)) onTrack(event);
                }}
                className="relative col-span-2 h-8 cursor-pointer touch-none rounded-sm outline-offset-2 focus-visible:outline-2 focus-visible:outline-ring sm:col-span-1"
              >
                <span className="absolute inset-x-0 top-[14px] h-1 rounded-full bg-muted" />
                <span
                  className="absolute top-[14px] left-0 h-1 rounded-l-full bg-border"
                  style={{ width: `${share(replay.freeze_end_tick)}%` }}
                />
                <span
                  ref={doneRef}
                  className="absolute top-[14px] left-0 h-1 rounded-full bg-foreground/55"
                  style={{ width: `${share(tick)}%` }}
                />
                {replay.kills.map((kill) => (
                  <span
                    key={`${kill.tick}-${kill.victim}`}
                    title={fill(labels.markKill, {
                      attacker: name(kill.attacker),
                      victim: name(kill.victim),
                      time: roundTime(kill.tick),
                    })}
                    className={cn(
                      "absolute top-0 h-3 w-0.5 -translate-x-1/2 rounded-full",
                      byId.get(kill.attacker ?? "")?.side === "CT" ? "bg-side-ct" : "bg-side-t",
                    )}
                    style={{ left: `${share(kill.tick)}%` }}
                  />
                ))}
                {replay.bomb.events
                  .filter((event) => event.type === "planted")
                  .map((event) => (
                    <span
                      key={event.tick}
                      title={fill(labels.markPlant, { time: roundTime(event.tick) })}
                      className="absolute top-[22px] size-2 -translate-x-1/2 rotate-45 rounded-[1px] bg-loss"
                      style={{ left: `${share(event.tick)}%` }}
                    />
                  ))}
                {focusTick !== null && (
                  <span
                    title={labels.markFocus}
                    className="absolute -top-1 size-2.5 -translate-x-1/2 rounded-full border-2 border-card bg-highlight"
                    style={{ left: `${share(focusTick)}%` }}
                  />
                )}
                <span
                  ref={headRef}
                  className="absolute top-[9px] h-3.5 w-1 -translate-x-1/2 rounded-full bg-foreground"
                  style={{ left: `${share(tick)}%` }}
                />
              </div>
              <fieldset className="col-start-2 row-start-1 m-0 inline-flex justify-self-end rounded-md border border-border bg-card p-0.5 sm:col-start-3">
                <legend className="sr-only">{labels.speed}</legend>
                {SPEEDS.map((value) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={speed === value}
                    onClick={() => setSpeed(value)}
                    className="h-6 rounded-sm px-2 text-xs text-muted-foreground tabular-nums aria-pressed:bg-highlight-soft aria-pressed:font-semibold aria-pressed:text-foreground"
                  >
                    {new Intl.NumberFormat(locale).format(value)}×
                  </button>
                ))}
              </fieldset>
            </div>
            <p className="flex flex-wrap gap-x-3.5 gap-y-1 px-3 pb-2.5 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1.5">
                <i aria-hidden="true" className="size-2 rounded-full bg-side-ct" />
                CT
              </span>
              <span className="inline-flex items-center gap-1.5">
                <i aria-hidden="true" className="size-2 rounded-full bg-side-t" />T
              </span>
              <span>{labels.legendKill}</span>
              <span>{labels.legendBomb}</span>
              {focusTick !== null && (
                <span className="inline-flex items-center gap-1.5">
                  <i aria-hidden="true" className="size-2 rounded-full bg-highlight" />
                  {labels.legendFocus}
                </span>
              )}
              <span className="hidden sm:inline">{labels.keys}</span>
            </p>
          </>
        )}
      </section>
      {replay && sample && (
        <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-1 lg:gap-3">
          {(["CT", "T"] as const).map((side) => {
            const players = replay.players.filter((p) => p.side === side);
            const alive = players.filter((p) => nearest(p.alive, sample)).length;
            return (
              <section key={side} className="rounded-lg border border-border bg-card">
                <h2 className="flex items-center justify-between border-b border-line-soft px-3 py-2 text-[0.8125rem] font-semibold">
                  <span className="inline-flex items-center gap-1.5">
                    <i
                      aria-hidden="true"
                      className={cn(
                        "size-2 rounded-full",
                        side === "CT" ? "bg-side-ct" : "bg-side-t",
                      )}
                    />
                    {side}
                  </span>
                  <span className="font-normal text-muted-foreground">
                    {fill(labels.alive, { count: String(alive) })}
                  </span>
                </h2>
                <ul>
                  {players.map((p) => {
                    const up = Boolean(nearest(p.alive, sample));
                    const hp = up ? (nearest(p.hp, sample) ?? 0) : 0;
                    return (
                      <li
                        key={p.steamid}
                        className={cn(
                          "grid grid-cols-[minmax(0,1fr)] gap-x-2.5 gap-y-0.5 border-t border-line-soft px-3 py-1.5 text-[0.8125rem] first:border-t-0 lg:grid-cols-[minmax(0,1fr)_4rem]",
                          p.steamid === focus && "bg-highlight-soft",
                          !up && "text-muted-foreground",
                        )}
                      >
                        <span className={cn("truncate font-semibold", !up && "line-through")}>
                          {p.name}
                        </span>
                        <span className="truncate text-xs text-muted-foreground lg:col-start-1">
                          {up ? weapon(nearest(p.weapon, sample)) : "–"}
                        </span>
                        <span className="flex items-center gap-1.5 text-xs font-semibold lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:flex-col lg:items-end lg:justify-center lg:gap-1">
                          <span className="tabular-nums">{up ? hp : labels.dead}</span>
                          <span
                            aria-hidden="true"
                            className="h-1 w-full min-w-10 overflow-hidden rounded-full bg-muted lg:w-16"
                          >
                            <span
                              className="block h-full bg-foreground/70"
                              style={{ width: `${hp}%` }}
                            />
                          </span>
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </section>
            );
          })}
          <section className="col-span-2 rounded-lg border border-border bg-card lg:col-span-1">
            <h2 className="border-b border-line-soft px-3 py-2 text-[0.8125rem] font-semibold">
              {labels.kills}
            </h2>
            {replay.kills.some((kill) => kill.tick <= tick) ? (
              <ol className="max-h-56 overflow-auto py-1">
                {replay.kills
                  .filter((kill) => kill.tick <= tick)
                  .map((kill) => (
                    <li
                      key={`${kill.tick}-${kill.victim}`}
                      className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-2 px-3 py-1 text-[0.8125rem]"
                    >
                      <time className="font-mono text-xs text-muted-foreground">
                        {roundTime(kill.tick)}
                      </time>
                      <span>
                        <span className={cn("font-semibold", sideClass(kill.attacker))}>
                          {name(kill.attacker)}
                        </span>{" "}
                        <span className="text-xs text-muted-foreground">
                          {killWeapon(kill.weapon) ?? labels.knife}
                          {kill.headshot ? `, ${labels.headshot}` : ""}
                        </span>{" "}
                        <span aria-hidden="true">→</span>{" "}
                        <span className={cn("font-semibold", sideClass(kill.victim))}>
                          {name(kill.victim)}
                        </span>
                      </span>
                    </li>
                  ))}
              </ol>
            ) : (
              <p className="px-3 py-2 text-[0.8125rem] text-muted-foreground">{labels.noKills}</p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
