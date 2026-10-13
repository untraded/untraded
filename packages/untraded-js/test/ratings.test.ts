// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: MIT
import { describe, expect, it } from "vitest";

import { type MatchTotals, ratingHltv1 } from "../src/index.js";

describe("ratingHltv1", () => {
  it("rates the reference average player 1.0", () => {
    // 679 kills spread as 180 x 1K, 200 x 2K, 33 x 3K: KPR 0.679,
    // survival 0.317 and multi-kill points 1277 over 1000 rounds.
    const rating = ratingHltv1({
      rounds: 1000,
      kills: 679,
      deaths: 683,
      multikills: { 1: 180, 2: 200, 3: 33 },
    });
    expect(rating).toBeCloseTo(1, 9);
  });

  it("rates a better player higher", () => {
    expect(
      ratingHltv1({ rounds: 24, kills: 30, deaths: 12, multikills: { 1: 8, 2: 5, 3: 4 } }),
    ).toBeGreaterThan(1.5);
  });

  it("rejects zero rounds", () => {
    expect(() => ratingHltv1({ rounds: 0, kills: 0, deaths: 0, multikills: {} })).toThrow(
      RangeError,
    );
  });

  it("rejects an invalid multikill key", () => {
    const invalid = { rounds: 10, kills: 6, deaths: 5, multikills: { 6: 1 } } as unknown;
    expect(() => ratingHltv1(invalid as MatchTotals)).toThrow(RangeError);
  });
});
