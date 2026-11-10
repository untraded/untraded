// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import type { MatchSummary, PlayerLine } from "../src/lib/api";
import {
  lineValue,
  MIN_ROUNDS,
  norm,
  previousMatches,
  quantile,
  selfRows,
  signed,
} from "../src/lib/self-norm";

const LINE: PlayerLine = {
  kills: 20,
  deaths: 15,
  adr: 80,
  kast: 70,
  hltv1: 1.1,
  untraded_deaths: 6,
  untraded: 1.05,
  level: 1.02,
};

/** Match `n`, played `n` hours before a fixed instant (so a larger `n` is older). */
const match = (n: number, over: Partial<MatchSummary> = {}): MatchSummary => ({
  id: `m${n}`,
  played_at: new Date(Date.UTC(2026, 10, 10) - n * 3_600_000).toISOString(),
  ended_at: null,
  mode: "premier",
  status: "ready",
  map: "de_mirage",
  score_a: 13,
  score_b: 11,
  rounds_played: 24,
  my_team: "A",
  my_result: "win",
  my_line: LINE,
  ...over,
});

const list = (count: number) => Array.from({ length: count }, (_, n) => match(n));

describe("previousMatches", () => {
  it("takes the matches after the target in the list, newest first, at most `count`", () => {
    const found = previousMatches(list(50), match(5), 30);
    expect(found).toHaveLength(30);
    expect(found[0]?.id).toBe("m6");
    expect(found.at(-1)?.id).toBe("m35");
  });

  it("never takes the target itself nor a later match", () => {
    const found = previousMatches(list(10), match(4));
    expect(found.map((m) => m.id)).toEqual(["m5", "m6", "m7", "m8", "m9"]);
  });

  it("leaves out matches not ready, without the player's line, undated or cut short", () => {
    const items = [
      match(0),
      match(1, { status: "failed" }),
      match(2, { my_line: null }),
      match(3, { played_at: null }),
      match(4, { rounds_played: MIN_ROUNDS - 1 }),
      match(5, { rounds_played: null }),
      match(6, { rounds_played: MIN_ROUNDS }),
    ];
    expect(previousMatches(items, match(0)).map((m) => m.id)).toEqual(["m6"]);
  });

  it("counts a match seen twice in the pages once", () => {
    const found = previousMatches([match(0), match(1), match(2), match(2), match(3)], match(0));
    expect(found.map((m) => m.id)).toEqual(["m1", "m2", "m3"]);
  });

  it("keeps the ready copy of a match seen twice", () => {
    const items = [match(0), match(1, { status: "parsing" }), match(1)];
    expect(previousMatches(items, match(0)).map((m) => m.id)).toEqual(["m1"]);
  });

  it("falls back on the date while the target is not in the list read so far", () => {
    const found = previousMatches([match(1), match(2), match(3)], match(2, { id: "elsewhere" }));
    expect(found.map((m) => m.id)).toEqual(["m3"]);
  });

  it("finds nothing before the oldest match, or before a target without a date", () => {
    expect(previousMatches(list(5), match(4))).toEqual([]);
    expect(previousMatches(list(5), { id: "x", played_at: null })).toEqual([]);
  });
});

describe("quantile", () => {
  it("interpolates linearly between the order statistics, as numpy does by default", () => {
    const values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    // numpy.quantile(range(1, 11), [0.1, 0.5, 0.9]) == [1.9, 5.5, 9.1]
    expect(quantile(values, 0.1)).toBeCloseTo(1.9, 10);
    expect(quantile(values, 0.5)).toBeCloseTo(5.5, 10);
    expect(quantile(values, 0.9)).toBeCloseTo(9.1, 10);
    expect(quantile([4], 0.9)).toBe(4);
    expect(quantile([], 0.5)).toBeNaN();
  });
});

describe("norm", () => {
  it("gives the count, mean, median and percentiles, whatever the order of the values", () => {
    const found = norm([10, 1, 9, 2, 8, 3, 7, 4, 6, 5]);
    expect(found).toMatchObject({ count: 10, mean: 5.5, median: 5.5 });
    expect(found?.p10).toBeCloseTo(1.9, 10);
    expect(found?.p90).toBeCloseTo(9.1, 10);
  });

  it("is null without values and ignores what is not a number", () => {
    expect(norm([])).toBeNull();
    expect(norm([Number.NaN, 2, Number.POSITIVE_INFINITY])?.count).toBe(1);
  });
});

describe("lineValue", () => {
  it("reads the five figures, the deaths untraded per round played", () => {
    const m = match(0);
    expect(lineValue(m, "untraded")).toBe(1.05);
    expect(lineValue(m, "adr")).toBe(80);
    expect(lineValue(m, "kast")).toBe(70);
    expect(lineValue(m, "kd")).toBe(5);
    expect(lineValue(m, "untraded_deaths")).toBeCloseTo(0.25, 10);
  });

  it("is null when the line lacks what the figure needs", () => {
    expect(lineValue(match(0, { my_line: null }), "adr")).toBeNull();
    expect(lineValue(match(0, { my_line: { ...LINE, untraded: null } }), "untraded")).toBeNull();
    expect(lineValue(match(0, { my_line: { ...LINE, deaths: null } }), "kd")).toBeNull();
    expect(lineValue(match(0, { rounds_played: 0 }), "untraded_deaths")).toBeNull();
    expect(lineValue(match(0, { rounds_played: null }), "untraded_deaths")).toBeNull();
  });
});

describe("selfRows", () => {
  /** Ten previous matches whose ADR runs from 61 to 70. */
  const previous = Array.from({ length: 10 }, (_, n) =>
    match(n + 1, { my_line: { ...LINE, adr: 61 + n, untraded_deaths: n % 4 } }),
  );

  it("places the match on the band of the previous values, gap to their mean", () => {
    const row = selfRows(match(0, { my_line: { ...LINE, adr: 80 } }), previous)[1];
    expect(row?.id).toBe("adr");
    expect(row?.norm?.mean).toBeCloseTo(65.5, 10);
    expect(row?.gap).toBeCloseTo(14.5, 10);
    expect(row?.position?.zone).toBe(4);
    expect(row?.missing).toBeNull();
  });

  it("reverses the axis for the deaths untraded: fewer is better", () => {
    const none = selfRows(match(0, { my_line: { ...LINE, untraded_deaths: 0 } }), previous)[4];
    expect(none?.id).toBe("untraded_deaths");
    expect(none?.better).toBe("lower");
    expect(none?.gap).toBeLessThan(0);
    expect(none?.position?.zone).toBeGreaterThanOrEqual(3);
  });

  it("draws no ruler below the floor of previous values, but keeps the mean and the gap", () => {
    const row = selfRows(match(0), previous.slice(0, 9))[1];
    expect(row?.position).toBeNull();
    expect(row?.missing).toBe("few");
    expect(row?.norm?.count).toBe(9);
    expect(row?.gap).not.toBeNull();
  });

  it("says why: no value in the match, no previous value, values that do not spread", () => {
    const rows = selfRows(match(0, { my_line: { ...LINE, untraded: null } }), previous);
    expect(rows[0]).toMatchObject({ missing: "noValue", gap: null, position: null });
    // Every previous KAST is 70: no band.
    expect(rows[2]?.missing).toBe("flat");
    expect(selfRows(match(0), [])[1]).toMatchObject({ missing: "noHistory", norm: null });
  });
});

describe("signed", () => {
  it("always signs, with the minus sign, and drops the sign of what rounds to zero", () => {
    expect(signed(0.114, "fr", 2)).toBe("+0,11");
    expect(signed(-1.26, "en", 1)).toBe("−1.3");
    expect(signed(-0.004, "en", 2)).toBe("0.00");
    expect(signed(null, "en")).toBe("–");
  });
});
