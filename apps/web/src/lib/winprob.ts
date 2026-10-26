// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The win-probability curve of a round replay (`winprob`, format 2), the parts that need no
// browser (tested): the curve over the whole round, the chance at a tick, and the actions that
// moved it.

import type { Replay, ReplaySwing, ReplayWinProb, Side } from "./replay";

/** An action that moved the curve: a kill, a plant or a defuse. */
export interface WinProbEvent {
  tick: number;
  event: ReplaySwing["event"];
  /** How much it moved the counter-terrorists' chance, after minus before (-1 to 1). */
  ct: number;
  /** The side it helped. */
  gainer: Side;
  /** Each player's share, the largest first: the credited ones, then the debited victim. */
  credits: ReplaySwing[];
}

/** Below this move (in chance, 0 to 1), a kill is not marked on the curve. */
export const MARKED = 0.1;

/** How many key moments the viewer lists under the curve. */
export const MOMENTS = 3;

/** The curve over the whole round: flat from the round's start to the first point (the freeze
 * time), then the model's points. */
export function curve(replay: Replay, winprob: ReplayWinProb): { tick: number; p: number }[] {
  const points = winprob.ticks.map((tick, i) => ({ tick, p: winprob.p_ct[i] ?? 0.5 }));
  const first = points[0];
  return first && first.tick > replay.start_tick
    ? [{ tick: replay.start_tick, p: first.p }, ...points]
    : points;
}

/** The counter-terrorists' chance at a tick: the last point at or before it. */
export function chanceAt(winprob: ReplayWinProb, tick: number): number {
  let found = winprob.p_ct[0] ?? 0.5;
  for (let i = 0; i < winprob.ticks.length; i++) {
    if ((winprob.ticks[i] ?? 0) > tick) break;
    found = winprob.p_ct[i] ?? found;
  }
  return found;
}

/** The actions of the round, in order: one per tick and kind, the swings grouped under it. The
 * move is read on the curve, which steps on the event's tick (a point before, a point after). */
export function events(winprob: ReplayWinProb): WinProbEvent[] {
  const grouped = new Map<string, WinProbEvent>();
  for (const swing of winprob.swings) {
    const key = `${swing.tick}-${swing.event}`;
    const found = grouped.get(key);
    if (found) found.credits.push(swing);
    else
      grouped.set(key, {
        tick: swing.tick,
        event: swing.event,
        ct: 0,
        gainer: "CT",
        credits: [swing],
      });
  }
  return [...grouped.values()]
    .map((event) => {
      const first = winprob.ticks.indexOf(event.tick);
      const last = winprob.ticks.lastIndexOf(event.tick);
      const ct =
        first >= 0 && last > first
          ? (winprob.p_ct[last] ?? 0) - (winprob.p_ct[first] ?? 0)
          : // No step on the curve: the credited side's swings say how much it moved.
            event.credits
              .filter((c) => c.swing > 0)
              .reduce((sum, c) => sum + (c.side === "CT" ? c.swing : -c.swing), 0);
      return {
        ...event,
        ct,
        gainer: (ct >= 0 ? "CT" : "T") as Side,
        credits: [...event.credits].sort((a, b) => b.swing - a.swing),
      };
    })
    .sort((a, b) => a.tick - b.tick);
}

/** The actions marked on the curve: every plant and defuse, and the kills that moved it enough. */
export function marked(list: WinProbEvent[]): WinProbEvent[] {
  return list.filter((e) => e.event !== "kill" || Math.abs(e.ct) >= MARKED);
}

/** The actions that weighed most on the round, the heaviest first. */
export function keyMoments(list: WinProbEvent[], count = MOMENTS): WinProbEvent[] {
  return [...list].sort((a, b) => Math.abs(b.ct) - Math.abs(a.ct)).slice(0, count);
}

/** A share of the chance as points, signed: `+35`, `−8`. */
export function points(value: number): string {
  const rounded = Math.round(Math.abs(value) * 100);
  return rounded === 0 ? "0" : `${value > 0 ? "+" : "−"}${rounded}`;
}
