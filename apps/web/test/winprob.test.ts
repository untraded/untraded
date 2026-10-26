// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import type { Replay, ReplayWinProb } from "../src/lib/replay";
import { chanceAt, curve, events, keyMoments, marked, points } from "../src/lib/winprob";

// A round: the freeze ends at 100; a kill at 300 helps the CT (0.5 → 0.7), a small one at 400
// helps the T (0.7 → 0.65), the bomb is planted at 500 (0.65 → 0.4), the T win at 800.
const winprob: ReplayWinProb = {
  model: "1.0",
  ticks: [100, 200, 300, 300, 400, 400, 500, 500, 600, 800],
  p_ct: [0.5, 0.5, 0.5, 0.7, 0.7, 0.65, 0.65, 0.4, 0.38, 0],
  swings: [
    { tick: 300, event: "kill", player: "1", side: "CT", swing: 0.2 },
    { tick: 300, event: "kill", player: "6", side: "T", swing: -0.2 },
    { tick: 400, event: "kill", player: "7", side: "T", swing: 0.04 },
    { tick: 400, event: "kill", player: "8", side: "T", swing: 0.01 },
    { tick: 400, event: "kill", player: "2", side: "CT", swing: -0.05 },
    { tick: 500, event: "plant", player: "7", side: "T", swing: 0.25 },
  ],
};
const replay = { start_tick: 0, freeze_end_tick: 100, end_tick: 800 } as Replay;

describe("winprob", () => {
  it("draws the curve from the round's start", () => {
    const points = curve(replay, winprob);
    expect(points[0]).toEqual({ tick: 0, p: 0.5 });
    expect(points.at(-1)).toEqual({ tick: 800, p: 0 });
  });

  it("reads the chance at a tick, after the step on an event's tick", () => {
    expect(chanceAt(winprob, 50)).toBe(0.5);
    expect(chanceAt(winprob, 300)).toBe(0.7);
    expect(chanceAt(winprob, 450)).toBe(0.65);
  });

  it("groups the swings by action and reads the move on the curve", () => {
    const list = events(winprob);
    expect(list.map((e) => [e.tick, e.event, Number(e.ct.toFixed(2)), e.gainer])).toEqual([
      [300, "kill", 0.2, "CT"],
      [400, "kill", -0.05, "T"],
      [500, "plant", -0.25, "T"],
    ]);
    expect(list[1]?.credits.map((c) => c.player)).toEqual(["7", "8", "2"]);
  });

  it("marks plants, defuses and the kills that moved the chance enough", () => {
    const list = events(winprob);
    expect(marked(list).map((e) => e.tick)).toEqual([300, 500]);
    expect(keyMoments(list, 2).map((e) => e.tick)).toEqual([500, 300]);
  });

  it("writes shares as signed points", () => {
    expect(points(0.349)).toBe("+35");
    expect(points(-0.08)).toBe("−8");
    expect(points(0.001)).toBe("0");
  });
});
