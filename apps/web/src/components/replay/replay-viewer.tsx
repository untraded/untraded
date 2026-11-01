// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Pause, Play, RotateCcw, RotateCw } from "lucide-react";
import {
  type KeyboardEvent,
  memo,
  type PointerEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { preload } from "react-dom";
import { Button } from "@/components/ui/button";
import { PUBLIC_API_PATH } from "@/lib/api-path";
import { cn } from "@/lib/cn";
import {
  clock,
  clockText,
  hasLevels,
  killStory,
  killWeapon,
  type Level,
  levelAt,
  momentKill,
  nearest,
  playbackStep,
  RADAR_MAPS,
  REPLAY_VERSION,
  type Replay,
  radarSrc,
  sampleAt,
  startTick,
  TWO_LEVELS,
  weaponKind,
} from "@/lib/replay";
import type { Scene, SceneColors } from "./scene";
import { WinProbChart, type WinProbLabels } from "./winprob-chart";

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
  playMoment: string;
  /** `{seconds}`; `{time}`; `{when}` and `{event}`; then the event: a kill, else the moment. */
  momentSoon: string;
  momentAt: string;
  momentLine: string;
  momentKilled: string;
  momentKills: string;
  momentOther: string;
  /** A death with no attacker (`{victim}`, `{cause}`), and its causes; a suicide. */
  momentDies: string;
  causeBomb: string;
  causeWorld: string;
  momentSuicideGrenade: string;
  momentSuicide: string;
  /** `{attacker}`, `{victim}` and `{time}` are replaced by the viewer. */
  markKill: string;
  winprob: WinProbLabels;
  /** Said instead of the curve for a round the model does not cover. */
  noWinprob: string;
}

/** Where the win-probability model is explained. */
const WINPROB_METHOD = "https://github.com/untraded/untraded/blob/main/docs/winprob.md";

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

/** The scene's code, PixiJS with it: never imported statically, so it stays out of the page. */
const loadScene = () => import("./scene");

/** A tick's place on the timeline, in % of the round. Within the round: an event can come after
 * its last tick (a bomb planted as it ends). */
const shareOf = (replay: Replay, t: number) =>
  Math.min(
    100,
    Math.max(0, ((t - replay.start_tick) / (replay.end_tick - replay.start_tick)) * 100),
  );

/** The timeline's marks: kills, plants and the moment to review. They do not move with the
 * playback, so they are not rendered again with it. */
const TimelineMarks = memo(function TimelineMarks({
  replay,
  focusTick,
  name,
  roundTime,
  labels,
}: {
  replay: Replay;
  focusTick: number | null;
  name: (steamid: string | null) => string;
  roundTime: (tick: number) => string;
  labels: ViewerLabels;
}) {
  const marks = useMemo(() => {
    const sides = new Map(replay.players.map((p) => [p.steamid, p.side]));
    return {
      kills: replay.kills.map((kill) => ({
        key: `${kill.tick}-${kill.victim}`,
        title: fill(labels.markKill, {
          attacker: name(kill.attacker),
          victim: name(kill.victim),
          time: roundTime(kill.tick),
        }),
        ct: sides.get(kill.attacker ?? "") === "CT",
        left: shareOf(replay, kill.tick),
      })),
      plants: replay.bomb.events
        .filter((event) => event.type === "planted")
        .map((event) => ({
          key: event.tick,
          title: fill(labels.markPlant, { time: roundTime(event.tick) }),
          left: shareOf(replay, event.tick),
        })),
    };
  }, [replay, name, roundTime, labels]);
  return (
    <>
      {marks.kills.map((kill) => (
        <span
          key={kill.key}
          title={kill.title}
          className={cn(
            "absolute top-0 h-3 w-0.5 -translate-x-1/2 rounded-full",
            kill.ct ? "bg-side-ct" : "bg-side-t",
          )}
          style={{ left: `${kill.left}%` }}
        />
      ))}
      {marks.plants.map((plant) => (
        <span
          key={plant.key}
          title={plant.title}
          className="absolute top-[22px] size-2 -translate-x-1/2 rotate-45 rounded-[1px] bg-loss"
          style={{ left: `${plant.left}%` }}
        />
      ))}
      {focusTick !== null && (
        <span
          title={labels.markFocus}
          className="absolute -top-1 size-2.5 -translate-x-1/2 rounded-full border-2 border-card bg-highlight"
          style={{ left: `${shareOf(replay, focusTick)}%` }}
        />
      )}
    </>
  );
});

type Speed = (typeof SPEEDS)[number];

/** The playback speeds, rendered again only when the speed changes. */
const SpeedButtons = memo(function SpeedButtons({
  speed,
  onSpeed,
  locale,
  label,
}: {
  speed: Speed;
  onSpeed: (speed: Speed) => void;
  locale: string;
  label: string;
}) {
  const format = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  return (
    <fieldset className="col-start-2 row-start-1 m-0 inline-flex justify-self-end rounded-md border border-border bg-card p-0.5 sm:col-start-3">
      <legend className="sr-only">{label}</legend>
      {SPEEDS.map((value) => (
        <button
          key={value}
          type="button"
          aria-pressed={speed === value}
          onClick={() => onSpeed(value)}
          className="h-6 rounded-sm px-2 text-xs text-muted-foreground tabular-nums aria-pressed:bg-highlight-soft aria-pressed:font-semibold aria-pressed:text-foreground"
        >
          {format.format(value)}×
        </button>
      ))}
    </fieldset>
  );
});

/**
 * Replays a round from above: the radar, the players, grenades and bomb, with a timeline, speeds,
 * levels, the teams and the kill feed. Opens on `start` (a tick) with `focus` highlighted.
 */
export function ReplayViewer({
  matchId,
  round,
  map,
  start,
  moment,
  focus,
  labels,
  locale,
}: {
  matchId: string;
  round: number;
  /** The match's map, known before the replay: its radar is fetched alongside. */
  map: string | null;
  start: number | null;
  /** The moment to review's event, when the link has it; else 5 s after `start`. */
  moment: number | null;
  focus: string | null;
  labels: ViewerLabels;
  locale: string;
}) {
  const [replay, setReplay] = useState<Replay | null>(null);
  const [problem, setProblem] = useState<"missing" | "failed" | "noGraphics" | null>(null);
  const [tick, setTick] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<Speed>(1);
  const [chosenLevel, setChosenLevel] = useState<Level | null>(null);
  const host = useRef<HTMLDivElement>(null);
  const probe = useRef<HTMLSpanElement>(null);
  const scene = useRef<Scene | null>(null);
  const tickRef = useRef(0);
  const playRef = useRef({ playing: false, speed: 1 as number });
  const viewRef = useRef<{ focus: string | null; level: Level }>({ focus, level: "upper" });
  const headRef = useRef<HTMLSpanElement>(null);
  const doneRef = useRef<HTMLSpanElement>(null);
  /** Where "Play the moment" pauses: a little after the moment, so it is seen, then still. */
  const stopRef = useRef<number | null>(null);
  /** Asks the scene for a frame: a redraw when paused, the loop's start when playing. */
  const wakeRef = useRef<() => void>(() => {});

  // The radar, fetched while the replay is (the scene loads it the same way, so it finds it).
  if (map && RADAR_MAPS.has(map)) {
    preload(radarSrc(map, "upper"), { as: "fetch", crossOrigin: "anonymous" });
    if (TWO_LEVELS.has(map)) {
      preload(radarSrc(map, "lower"), { as: "fetch", crossOrigin: "anonymous" });
    }
  }
  // The scene's code too: it does not need the replay to come.
  useEffect(() => {
    // A failure is said when the scene is made, with the replay.
    loadScene().catch(() => {});
  }, []);

  // The replay, from the API (gzipped, and cached by the browser: it never changes). The format
  // version is in the address, so a new viewer never reads a replay cached for the old one.
  useEffect(() => {
    let live = true;
    setReplay(null);
    setProblem(null);
    fetch(
      `${PUBLIC_API_PATH}/matches/${encodeURIComponent(matchId)}/rounds/${round}/replay?v=${REPLAY_VERSION}`,
    )
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

  // The scene, and the clock that moves it while playing. Paused, it draws only when what it shows
  // changes (a seek, the level, the focus, the colours, the size): no frame is asked for otherwise.
  useEffect(() => {
    if (!replay || !host.current || !probe.current) return;
    let live = true;
    let frame = 0;
    let last: number | null = null;
    let shown = 0;
    const box = host.current;
    const colors = readColors(probe.current);
    const draw = () => scene.current?.draw({ tick: tickRef.current, ...viewRef.current });
    const halt = () => {
      playRef.current = { ...playRef.current, playing: false };
      setPlaying(false);
      setTick(tickRef.current);
    };
    // One frame: the playback moves if it plays, the scene is drawn, and the next frame is asked
    // for only while it plays.
    const step = (now: number) => {
      frame = 0;
      if (!live) return;
      if (playRef.current.playing) {
        if (last !== null) {
          tickRef.current = playbackStep(
            replay,
            tickRef.current,
            now - last,
            playRef.current.speed,
          );
          if (stopRef.current !== null && tickRef.current >= stopRef.current) {
            stopRef.current = null;
            halt();
          }
          if (tickRef.current >= replay.end_tick) halt();
          placeHead(replay, tickRef.current, headRef.current, doneRef.current);
          if (now - shown > PANEL_EVERY) {
            shown = now;
            setTick(tickRef.current);
          }
        }
        last = now;
      } else {
        last = null;
      }
      draw();
      if (playRef.current.playing) frame = requestAnimationFrame(step);
    };
    wakeRef.current = () => {
      if (live && scene.current && frame === 0) frame = requestAnimationFrame(step);
    };
    loadScene()
      .then(({ createScene }) => createScene(box, replay, box.clientWidth || 600, colors))
      .then((made) => {
        if (!live) return made.destroy();
        scene.current = made;
        draw();
        if (playRef.current.playing) wakeRef.current();
      })
      .catch(() => live && setProblem("noGraphics"));
    const resize = new ResizeObserver(() => {
      scene.current?.resize(box.clientWidth);
      draw();
    });
    resize.observe(box);
    // A theme change (the user's choice, `data-theme` on `<html>`, or the system's): new colours.
    const recolor = () => {
      if (probe.current) scene.current?.setColors(readColors(probe.current));
      draw();
    };
    const themes = new MutationObserver(recolor);
    themes.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const dark = window.matchMedia("(prefers-color-scheme: dark)");
    dark.addEventListener("change", recolor);
    // A hidden tab gets no frames: back in view, the playback goes on from where it was.
    const visibility = () => {
      last = null;
    };
    document.addEventListener("visibilitychange", visibility);
    return () => {
      live = false;
      cancelAnimationFrame(frame);
      wakeRef.current = () => {};
      resize.disconnect();
      themes.disconnect();
      dark.removeEventListener("change", recolor);
      document.removeEventListener("visibilitychange", visibility);
      scene.current?.destroy();
      scene.current = null;
    };
  }, [replay]);

  // What is drawn changed, or the playback started: a frame, which goes on as the loop while it
  // plays. (Playing, the loop already draws each frame, and this asks for nothing more.)
  // biome-ignore lint/correctness/useExhaustiveDependencies: they are what triggers it, read by the scene through viewRef and playRef
  useEffect(() => {
    wakeRef.current();
  }, [playing, level, focus]);

  const seek = useCallback(
    (next: number) => {
      if (!replay) return;
      // Moving the playback by hand cancels the stop planned by "Play the moment".
      stopRef.current = null;
      tickRef.current = Math.min(replay.end_tick, Math.max(replay.start_tick, next));
      setTick(tickRef.current);
      placeHead(replay, tickRef.current, headRef.current, doneRef.current);
      wakeRef.current();
    },
    [replay],
  );

  function toggle() {
    if (!replay) return;
    stopRef.current = null;
    if (!playing && tickRef.current >= replay.end_tick) seek(replay.start_tick);
    // Paused, the panel shows exactly where the playback stopped.
    if (playing) setTick(tickRef.current);
    setPlaying(!playing);
  }

  // Positions of the timeline's playback, in % of the round.
  const share = (t: number) => (replay ? shareOf(replay, t) : 0);
  const byId = useMemo(() => new Map(replay?.players.map((p) => [p.steamid, p]) ?? []), [replay]);
  const bySide = useMemo(
    () => ({
      CT: replay?.players.filter((p) => p.side === "CT") ?? [],
      T: replay?.players.filter((p) => p.side === "T") ?? [],
    }),
    [replay],
  );
  // Stable, for the parts that do not follow the playback (marks, the curve's static layer).
  const roundTime = useCallback(
    (t: number) => (replay ? clockText(clock(replay, t).seconds) : ""),
    [replay],
  );
  const name = useCallback(
    (steamid: string | null) =>
      steamid === null ? labels.world : (byId.get(steamid)?.name ?? "?"),
    [byId, labels.world],
  );
  // The event of the moment to review: from the link, else 5 s after the opening (reports open
  // 5 s before, unless the demo starts later). Only within the round.
  const eventTick = replay && start !== null ? (moment ?? start + 5 * replay.tickrate) : null;
  const focusTick =
    replay && eventTick !== null && eventTick >= replay.start_tick && eventTick <= replay.end_tick
      ? eventTick
      : null;
  const focusKill = replay && focusTick !== null ? momentKill(replay, focusTick, focus) : null;

  /** From where the viewer opened (5 s before) to a little after the moment, then pause. */
  function playMoment() {
    if (!replay || start === null || focusTick === null) return;
    const opened = startTick(replay, start);
    if (tickRef.current < opened || tickRef.current >= focusTick) seek(opened);
    stopRef.current = Math.min(
      replay.end_tick,
      (focusKill?.tick ?? focusTick) + 2 * replay.tickrate,
    );
    setPlaying(true);
  }

  if (problem) {
    return (
      <p role="alert" className="rounded-lg border border-border bg-card px-4 py-3 text-sm">
        {labels[problem]}
      </p>
    );
  }

  const now = replay ? clock(replay, tick) : null;
  const weapon = (index: number | null) => {
    const name = index === null ? null : (replay?.weapons[index] ?? null);
    const kind = weaponKind(name);
    return kind === "knife" ? labels.knife : kind === "c4" ? labels.c4 : (name ?? "–");
  };
  /** A kill in words: who killed whom with what, or how the player died. */
  const killText = (kill: NonNullable<typeof focusKill>) => {
    const story = killStory(kill, focus);
    const values = {
      attacker: name(kill.attacker),
      victim: name(kill.victim),
      weapon: killWeapon(kill.weapon) ?? labels.knife,
    };
    if (story.kind === "dies")
      return fill(labels.momentDies, {
        ...values,
        cause: story.cause === "bomb" ? labels.causeBomb : labels.causeWorld,
      });
    if (story.kind === "suicide")
      return fill(story.grenade ? labels.momentSuicideGrenade : labels.momentSuicide, values);
    return fill(story.kind === "kills" ? labels.momentKills : labels.momentKilled, values);
  };
  // The moment to review, said at the timeline: what happens, and in how long.
  const momentText = (() => {
    if (!replay || focusTick === null) return null;
    const at = focusKill?.tick ?? focusTick;
    const left = Math.ceil((at - tick) / replay.tickrate);
    const when =
      left > 0
        ? fill(labels.momentSoon, { seconds: String(left) })
        : fill(labels.momentAt, { time: roundTime(at) });
    const event = focusKill ? killText(focusKill) : labels.momentOther;
    return fill(labels.momentLine, { when, event });
  })();
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
            {momentText && (
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-border bg-highlight-soft px-3 py-2 text-sm">
                <Button size="sm" className="gap-1.5" onClick={playMoment}>
                  <Play aria-hidden="true" />
                  {labels.playMoment}
                </Button>
                <span className="inline-flex items-center gap-2">
                  <i aria-hidden="true" className="size-2 shrink-0 rounded-full bg-highlight" />
                  <span className="tabular-nums">{momentText}</span>
                </span>
              </div>
            )}
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
                <TimelineMarks
                  replay={replay}
                  focusTick={focusTick}
                  name={name}
                  roundTime={roundTime}
                  labels={labels}
                />

                <span
                  ref={headRef}
                  className="absolute top-[9px] h-3.5 w-1 -translate-x-1/2 rounded-full bg-foreground"
                  style={{ left: `${share(tick)}%` }}
                />
              </div>
              {/* Under the timeline and at its scale: the same column. */}
              <div className="col-span-2 sm:col-span-1 sm:col-start-2">
                {replay.winprob ? (
                  <WinProbChart
                    replay={replay}
                    winprob={replay.winprob}
                    tick={tick}
                    onSeek={seek}
                    roundTime={roundTime}
                    name={name}
                    labels={labels.winprob}
                    method={WINPROB_METHOD}
                  />
                ) : (
                  <p className="text-xs text-muted-foreground">{labels.noWinprob}</p>
                )}
              </div>
              <SpeedButtons speed={speed} onSpeed={setSpeed} locale={locale} label={labels.speed} />
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
            const players = bySide[side];
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
