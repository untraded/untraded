// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import type { Advice, MatchDetail, MetricValue, Round } from "../src/lib/api";
import {
  bySide,
  minutes,
  momentHref,
  prioritiesIn,
  roundsBySide,
  sideOf,
  wonRound,
} from "../src/lib/match";

const round = (n: number, ct: "A" | "B", winner: "A" | "B" | null): Round => ({
  round: n,
  winner_side: winner === null ? null : winner === ct ? "CT" : "T",
  winner_team: winner,
  reason: "elimination",
  ct_team: ct,
  score_a: 0,
  score_b: 0,
  is_overtime: false,
  bomb_site: null,
  bomb_planted: false,
});

const match = {
  id: "m1",
  my_team: "B",
  rounds: [round(1, "A", "A"), round(2, "A", "B"), round(13, "B", null)],
} as MatchDetail;

const advice = (priority: number, events: [string, number, number][]): Advice =>
  ({
    id: `a${priority}`,
    priority,
    rule_id: "trade.untraded_deaths",
    evidence: events.map(([match_id, round, goto_tick]) => ({
      match_id,
      round,
      tick: goto_tick + 320,
      goto_tick,
    })),
  }) as Advice;

describe("match", () => {
  it("keeps the priorities that flag this match, in order, one box per round", () => {
    const found = prioritiesIn(
      [
        advice(2, [
          ["m1", 7, 900],
          ["m1", 3, 500],
          ["m1", 3, 400],
        ]),
        advice(3, [["other", 1, 100]]),
        advice(1, [["m1", 2, 200]]),
      ],
      "m1",
    );
    expect(found.map((p) => p.advice.priority)).toEqual([1, 2]);
    expect(found[1]?.rounds).toEqual([
      { round: 3, tick: 400, event: 720, moments: 2 },
      { round: 7, tick: 900, event: 1220, moments: 1 },
    ]);
  });

  it("links a moment with its event and its priority", () => {
    expect(momentHref("m1", 3, { tick: 0, event: 120, rule: "util.team_flash" })).toBe(
      "/matches/m1/rounds/3?t=0&e=120&p=util.team_flash",
    );
  });

  it("reads sides and results from the player's team", () => {
    expect(sideOf(match, 1)).toBe("T");
    expect(sideOf(match, 13)).toBe("CT");
    expect(sideOf(match, 99)).toBeNull();
    expect(wonRound(match, 1)).toBe(false);
    expect(wonRound(match, 2)).toBe(true);
    expect(wonRound(match, 13)).toBeNull();
    expect(roundsBySide(match)).toEqual({ CT: 1, T: 2 });
    expect(roundsBySide({ ...match, my_team: null })).toEqual({ CT: 0, T: 0 });
  });

  it("splits a metric by side, undefined when missing", () => {
    const value = (scope: MetricValue["scope"], v: number | null): MetricValue => ({
      metric_id: "base.adr",
      version: "1.0.0",
      name: "ADR",
      unit: "damage_per_round",
      better: "higher",
      scope,
      value: v,
    });
    const metrics = [value("match", 80), value("ct", 90), value("t", null)];
    expect(bySide(metrics, "base.adr")).toEqual({ ct: 90, t: null });
    expect(bySide(metrics, "base.kast")).toEqual({ ct: undefined, t: undefined });
  });

  it("gives the length of a match in minutes", () => {
    expect(minutes("2026-10-20T12:00:00Z", "2026-10-20T12:38:20Z")).toBe(38);
    expect(minutes(null, "2026-10-20T12:38:00Z")).toBeNull();
    expect(minutes("2026-10-20T12:38:00Z", "2026-10-20T12:00:00Z")).toBeNull();
  });
});
