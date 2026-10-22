// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import {
  angleBetween,
  between,
  bombCarrier,
  clock,
  clockText,
  frameOf,
  hasLevels,
  levelAt,
  levelOf,
  sampleAt,
  startTick,
  weaponKind,
} from "../src/lib/replay";

const NUKE = { pos_x: -3453, pos_y: 2887, scale: 7, lower_below: -495 };
const bomb = {
  events: [
    { tick: 100, type: "picked_up" as const, player: "6", site: null },
    { tick: 200, type: "dropped" as const, player: "6", site: null },
    { tick: 300, type: "picked_up" as const, player: "7", site: null },
    { tick: 400, type: "planted" as const, player: "7", site: "A" },
  ],
  planted_at: null,
};

describe("replay", () => {
  it("finds the samples around a tick", () => {
    const ticks = [0, 4, 8, 12];
    expect(sampleAt(ticks, 6)).toEqual({ i0: 1, i1: 2, f: 0.5 });
    expect(sampleAt(ticks, 8)).toEqual({ i0: 2, i1: 3, f: 0 });
    expect(sampleAt(ticks, -5)).toEqual({ i0: 0, i1: 0, f: 0 });
    expect(sampleAt(ticks, 99)).toEqual({ i0: 3, i1: 3, f: 0 });
  });

  it("blends values and angles between samples", () => {
    const sample = { i0: 0, i1: 1, f: 0.25 };
    expect(between([100, 200], sample)).toBe(125);
    expect(between([null, 200], sample)).toBe(200);
    expect(between([null, null], sample)).toBeNull();
    // 350° to 10° goes through 0°, not back through 180°.
    expect(angleBetween([350, 10], { i0: 0, i1: 1, f: 0.5 })).toBe(360);
  });

  it("places world points with the map's transform", () => {
    const frame = frameOf({ radar: NUKE, players: [] });
    expect(frame.radar).toBe(true);
    expect(frame.toPixel(-3453, 2887)).toEqual([0, 0]);
    expect(frame.toPixel(-3453 + 700, 2887 - 1400)).toEqual([100, 200]);
    expect(frame.scale).toBeCloseTo(1 / 7);
  });

  it("fits the round in the square when the map has no transform", () => {
    const player = (x: (number | null)[], y: (number | null)[]) =>
      ({ x, y }) as unknown as Parameters<typeof frameOf>[0]["players"][number];
    const frame = frameOf({
      radar: null,
      players: [player([0, 1000], [0, 500]), player([null], [null])],
    });
    expect(frame.radar).toBe(false);
    const [left, mid] = frame.toPixel(0, 250);
    const [right] = frame.toPixel(1000, 250);
    expect(mid).toBeCloseTo(512);
    expect((left + right) / 2).toBeCloseTo(512);
    // A 6 % margin on each side of the widest extent.
    expect(right - left).toBeCloseTo(1024 / 1.12);
  });

  it("tells the level from the height, only on a two-level map", () => {
    expect(hasLevels({ radar: NUKE })).toBe(true);
    expect(hasLevels({ radar: { ...NUKE, lower_below: null } })).toBe(false);
    expect(hasLevels({ radar: null })).toBe(false);
    expect(levelOf({ radar: NUKE }, -600)).toBe("lower");
    expect(levelOf({ radar: NUKE }, -400)).toBe("upper");
    expect(levelOf({ radar: null }, -600)).toBe("upper");
  });

  it("reads the clock: buy time, round time, then the bomb", () => {
    const replay = { tickrate: 64, freeze_end_tick: 640, bomb: { ...bomb, events: [] } };
    expect(clock(replay, 0)).toEqual({ kind: "freeze", seconds: 10 });
    expect(clock(replay, 640 + 64 * 15)).toEqual({ kind: "round", seconds: 100 });
    expect(clock({ ...replay, bomb }, 400 + 64 * 10)).toEqual({ kind: "bomb", seconds: 30 });
    expect(clockText(65)).toBe("1:05");
    expect(clockText(4.2)).toBe("0:05");
    expect(clockText(-3)).toBe("0:00");
  });

  it("follows the bomb from carrier to carrier", () => {
    expect(bombCarrier({ bomb }, 150)).toBe("6");
    expect(bombCarrier({ bomb }, 250)).toBeNull();
    expect(bombCarrier({ bomb }, 350)).toBe("7");
    expect(bombCarrier({ bomb }, 450)).toBeNull();
  });

  it("opens where asked, within the round", () => {
    const round = { start_tick: 100, end_tick: 900, freeze_end_tick: 300 };
    expect(startTick(round, null)).toBe(300);
    expect(startTick(round, 500)).toBe(500);
    expect(startTick(round, 50)).toBe(100);
    expect(startTick(round, 5000)).toBe(900);
  });

  it("names every knife a knife", () => {
    expect(weaponKind("Butterfly Knife")).toBe("knife");
    expect(weaponKind("knife_t")).toBe("knife");
    expect(weaponKind("C4 Explosive")).toBe("c4");
    expect(weaponKind("AK-47")).toBeNull();
  });

  it("finds the level a player stands on, from their last known height", () => {
    const ticks = [0, 4, 8, 12];
    const player = (steamid: string, z: (number | null)[]) =>
      ({ steamid, z }) as unknown as Parameters<typeof levelAt>[0]["players"][number];
    const replay = {
      radar: NUKE,
      ticks,
      players: [player("up", [-400, -400, null, null]), player("down", [null, -600, -600, -600])],
    };
    expect(levelAt(replay, "up", 6)).toBe("upper");
    // No height yet at the opening sample: the next one counts, not a default.
    expect(levelAt(replay, "down", 0)).toBe("lower");
    // No height any more (dead): the last one counts.
    expect(levelAt(replay, "up", 12)).toBe("upper");
    expect(levelAt(replay, "nobody", 6)).toBe("upper");
    expect(levelAt({ ...replay, radar: { ...NUKE, lower_below: null } }, "down", 6)).toBe("upper");
  });
});
