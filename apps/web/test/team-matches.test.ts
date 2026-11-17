// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import type { TeamMatchDetail } from "@/lib/api";
import { asMatchDetail, isShared, teamScore } from "@/lib/team-matches";
import { readsMatches, teamHref, teamMatchHref } from "@/lib/teams";

const LINE = {
  kills: 20,
  deaths: 15,
  adr: 80,
  kast: 70,
  hltv1: 1.1,
  untraded_deaths: 3,
  untraded: 1.12,
  level: 1.04,
};

const detail = (over: Partial<TeamMatchDetail> = {}): TeamMatchDetail => ({
  id: "m1",
  played_at: "2026-11-16T20:00:00Z",
  ended_at: "2026-11-16T20:40:00Z",
  mode: "scrim",
  status: "ready",
  map: "de_nuke",
  score_a: 9,
  score_b: 13,
  rounds_played: 22,
  reason: "roster",
  our_team: "B",
  our_result: "win",
  team_players: [{ steam_id: "1", name: "Brindle", team: "B" }],
  team_a_name: null,
  team_b_name: null,
  tickrate: 64,
  unavailable: [],
  error: null,
  rounds: [],
  players: [
    {
      steam_id: "1",
      name: "Brindle",
      team: "B",
      rank: null,
      rounds_on_team: 22,
      line: LINE,
      member: true,
    },
  ],
  ...over,
});

describe("a team's match", () => {
  it("reads as a match page from our side, with no line of the player's", () => {
    const match = asMatchDetail(detail());
    expect(match.my_team).toBe("B");
    expect(match.my_result).toBe("win");
    expect(match.my_line).toBeNull();
    expect(match.players[0]).not.toHaveProperty("member");
    expect(match).not.toHaveProperty("our_team");
    expect(match).not.toHaveProperty("team_players");
  });

  it("gives the score from our side, or as it stands without a side", () => {
    expect(teamScore(detail())).toEqual([13, 9]);
    expect(teamScore(detail({ our_team: "A" }))).toEqual([9, 13]);
    expect(teamScore(detail({ our_team: null, reason: "shared" }))).toEqual([9, 13]);
    expect(teamScore(detail({ status: "parsing", score_a: null, score_b: null }))).toBeNull();
  });

  it("is shared only when a member shared it; the team's own uploads are its matches", () => {
    expect(isShared(detail({ reason: "shared" }))).toBe(true);
    expect(isShared(detail({ reason: "team" }))).toBe(false);
    expect(isShared(detail())).toBe(false);
  });

  it("has its address on the team's pages, open to roles that read matches", () => {
    expect(teamHref("north wind", "matches")).toBe("/teams/north%20wind/matches");
    expect(teamMatchHref("northwind", "a/b")).toBe("/teams/northwind/matches/a%2Fb");
    expect(readsMatches(["matches.read"])).toBe(true);
    expect(readsMatches(["*"])).toBe(true);
    expect(readsMatches(["review.comment"])).toBe(false);
  });
});
