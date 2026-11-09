// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { position, zoneTrend } from "../src/lib/position";

describe("position", () => {
  it("puts the median in the middle zone and the landmarks on their percentiles", () => {
    const p = position(71, 71, 58, 82, "higher");
    expect(p?.percentile).toBe(50);
    expect(p?.zone).toBe(2);
    expect(p?.at).toBeCloseTo(p?.median ?? -1, 6);
    expect(position(58, 71, 58, 82, "higher")?.percentile).toBe(10);
    expect(position(82, 71, 58, 82, "higher")?.percentile).toBe(90);
  });

  it("names the five zones from below to above", () => {
    const zones = [40, 60, 71, 78, 95].map((v) => position(v, 71, 58, 82, "higher")?.zone);
    expect(zones).toEqual([0, 1, 2, 3, 4]);
  });

  it("keeps the percentile between 1 and 99 far outside the band", () => {
    expect(position(-1000, 71, 58, 82, "higher")?.percentile).toBe(1);
    expect(position(1000, 71, 58, 82, "higher")?.percentile).toBe(99);
    expect(position(-1000, 71, 58, 82, "higher")?.at).toBe(0);
    expect(position(1000, 71, 58, 82, "higher")?.at).toBe(100);
  });

  it("reverses the axis and the zones when lower is better", () => {
    const low = position(0.05, 0.19, 0.1, 0.3, "lower");
    const high = position(0.5, 0.19, 0.1, 0.3, "lower");
    expect(low?.zone).toBe(4);
    expect(high?.zone).toBe(0);
    // Better is on the right: the small value is further right than the median.
    expect((low?.at ?? 0) > (low?.median ?? 100)).toBe(true);
    expect((high?.at ?? 100) < (high?.median ?? 0)).toBe(true);
    // The band keeps from < to whatever the direction.
    expect(low?.bandFrom).toBeLessThan(low?.bandTo ?? 0);
    const mirror = position(0.5, 0.19, 0.1, 0.3, "higher");
    expect(mirror?.zone).toBe(4);
    expect(mirror?.percentile).toBe(100 - (high?.percentile ?? 0));
  });

  it("falls back for a neutral metric, with no zone and no colour", () => {
    expect(position(5, 5, 3, 8, "neutral")).toBeNull();
  });

  it("falls back when a landmark is missing or not a number", () => {
    expect(position(5, 5, null, 8, "higher")).toBeNull();
    expect(position(5, 5, 3, undefined, "higher")).toBeNull();
    expect(position(null, 5, 3, 8, "higher")).toBeNull();
    expect(position(5, null, 3, 8, "higher")).toBeNull();
    expect(position(Number.NaN, 5, 3, 8, "higher")).toBeNull();
    expect(position(5, 5, 3, Number.POSITIVE_INFINITY, "higher")).toBeNull();
  });

  it("falls back for a band with no width", () => {
    expect(position(5, 5, 5, 5, "higher")).toBeNull();
  });

  it("puts inverted landmarks back in order", () => {
    expect(position(60, 71, 82, 58, "higher")).toEqual(position(60, 71, 58, 82, "higher"));
  });

  it("falls back when the median is outside the band", () => {
    expect(position(5, 20, 3, 8, "higher")).toBeNull();
    expect(position(5, 1, 3, 8, "higher")).toBeNull();
  });

  it("copes with a median on an edge of the band", () => {
    const p = position(0, 0, 0, 2, "higher");
    expect(p).not.toBeNull();
    expect(Number.isFinite(p?.at)).toBe(true);
    expect(p?.bandFrom).toBeLessThan(p?.bandTo ?? 0);
    const q = position(0, 2, 0, 2, "higher");
    expect(q?.percentile).toBe(10);
    expect(q?.zone).toBe(1);
  });

  it("puts a value on the median at 50 even when the median is on an edge of the band", () => {
    expect(position(0, 0, 0, 2, "higher")?.percentile).toBe(50);
    expect(position(0, 0, 0, 2, "higher")?.zone).toBe(2);
    expect(position(0, 0, 0, 2, "lower")?.zone).toBe(2);
    expect(position(2, 2, 0, 2, "higher")?.percentile).toBe(50);
    expect(position(1, 0, 0, 2, "higher")?.percentile).toBe(70);
    expect(position(-1, 0, 0, 2, "higher")?.zone).toBeLessThan(2);
  });

  it("handles negative values", () => {
    const p = position(-3, 0, -8, 6, "higher");
    expect(p?.zone).toBe(2);
    expect(position(-12, 0, -8, 6, "higher")?.zone).toBe(0);
    expect(position(9, 0, -8, 6, "higher")?.zone).toBe(4);
  });

  it("keeps every position on the axis", () => {
    for (const v of [-50, 0, 30, 58, 71, 82, 100, 500]) {
      const p = position(v, 71, 58, 82, "higher");
      for (const x of [p?.at, p?.median, p?.bandFrom, p?.bandTo]) {
        expect(x).toBeGreaterThanOrEqual(0);
        expect(x).toBeLessThanOrEqual(100);
      }
    }
  });

  it("reads zones as trends", () => {
    expect([0, 1, 2, 3, 4].map((z) => zoneTrend(z as 0 | 1 | 2 | 3 | 4))).toEqual([
      "worse",
      "worse",
      "same",
      "better",
      "better",
    ]);
  });
});
