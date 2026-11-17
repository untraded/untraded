// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { initials, rememberedTeam, spaceOf } from "@/lib/space";

const SLUGS = ["northwind", "ashgrove"];

describe("space", () => {
  it("reads a team's space from its pages, the player's own everywhere else", () => {
    expect(spaceOf("/teams/northwind", SLUGS)).toBe("northwind");
    expect(spaceOf("/teams/NorthWind/members", SLUGS)).toBe("northwind");
    expect(spaceOf("/teams/someone-else", SLUGS)).toBeNull();
    expect(spaceOf("/team/lineups", SLUGS)).toBeNull();
    expect(spaceOf("/matches", SLUGS)).toBeNull();
    expect(spaceOf("/teams/%E0%A4%A", SLUGS)).toBeNull();
  });

  it("brings back only a team that is still the player's", () => {
    expect(rememberedTeam("ashgrove", SLUGS)).toBe("ashgrove");
    expect(rememberedTeam("~personal", SLUGS)).toBeNull();
    expect(rememberedTeam("personal", ["personal"])).toBe("personal");
    expect(rememberedTeam("gone", SLUGS)).toBeNull();
    expect(rememberedTeam(undefined, SLUGS)).toBeNull();
  });

  it("makes a team's badge from its name", () => {
    expect(initials("Northwind")).toBe("NO");
    expect(initials("Ashgrove Academy")).toBe("AA");
    expect(initials("  ")).toBe("?");
  });
});
