// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { rate } from "@/components/teams/team-stats-view";
import { filtersOf, statsHref } from "@/lib/team-stats";

describe("team stats filters", () => {
  it("reads the filters of the address, anything else falling back to the defaults", () => {
    expect(filtersOf({})).toEqual({ map: null, days: 30, type: "all" });
    expect(filtersOf({ map: "de_nuke", days: "90", type: "scrim" })).toEqual({
      map: "de_nuke",
      days: 90,
      type: "scrim",
    });
    // Only the periods the page offers, the types the API takes, and a map's characters.
    expect(filtersOf({ days: "365", type: "premier", map: "../x" })).toEqual({
      map: null,
      days: 30,
      type: "all",
    });
    expect(filtersOf({ map: "DE_NUKE" }).map).toBeNull();
  });

  it("writes the filters, leaving the defaults out", () => {
    expect(statsHref("north-wind", { map: null, days: 30, type: "all" })).toBe(
      "/teams/north-wind/stats",
    );
    expect(statsHref("north-wind", { map: "de_nuke", days: 7, type: "official" })).toBe(
      "/teams/north-wind/stats?map=de_nuke&days=7&type=official",
    );
  });

  it("has no rate without a round", () => {
    expect(rate({ rounds: 0, won: 0 })).toBeNull();
    expect(rate({ rounds: 4, won: 3 })).toBe(0.75);
  });
});
