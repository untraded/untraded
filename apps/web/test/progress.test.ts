// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import type { Comparison, SessionSummary } from "../src/lib/api";
import { change, geometry, inPeriod, pickPeriod, series } from "../src/lib/progress";

const NOW = Date.parse("2026-10-25T20:00:00Z");
const DAY = 86_400_000;

const headline = (session: number, reference: number | null): Comparison => ({
  metric_id: "base.adr",
  version: "1.0.0",
  name: "ADR",
  unit: "damage_per_round",
  better: "higher",
  basis: "value",
  session,
  reference,
  delta: reference === null ? null : session - reference,
  cases: null,
  signed: false,
});

/** A session `daysAgo` days before NOW, newest first in the lists below. */
const session = (n: number, daysAgo: number, adr: number, enough = true): SessionSummary =>
  ({
    id: `s${n}`,
    started_at: new Date(NOW - daysAgo * DAY).toISOString(),
    enough,
    headlines: [headline(adr, 80)],
  }) as SessionSummary;

const list = [
  session(0, 1, 84),
  session(1, 10, 82, false),
  session(2, 40, 78),
  session(3, 100, 70),
];

describe("progress", () => {
  it("reads a period, defaulting to 30 days", () => {
    expect(pickPeriod(undefined)).toBe("days30");
    expect(pickPeriod("all")).toBe("all");
    expect(pickPeriod("year")).toBe("days30");
  });

  it("keeps the sessions of a period, oldest first", () => {
    expect(inPeriod(list, "days30", NOW).map((s) => s.id)).toEqual(["s1", "s0"]);
    expect(inPeriod(list, "days90", NOW).map((s) => s.id)).toEqual(["s2", "s1", "s0"]);
    expect(inPeriod(list, "all", NOW)).toHaveLength(4);
    expect(inPeriod(list, "last10", NOW).at(-1)?.id).toBe("s0");
  });

  it("builds a series, without the reference of a session that had none", () => {
    const line = series(inPeriod(list, "days90", NOW), "base.adr");
    expect(line?.points.map((p) => [p.value, p.reference])).toEqual([
      [78, 80],
      [82, null],
      [84, 80],
    ]);
    expect(series(list, "base.kast")).toBeNull();
  });

  it("says how much a figure moved, the better way positive", () => {
    const points = [
      { sessionId: "a", startedAt: "", value: 0.4, reference: null },
      { sessionId: "b", startedAt: "", value: null, reference: null },
      { sessionId: "c", startedAt: "", value: 0.3, reference: null },
    ];
    expect(change(points, "lower")).toBeCloseTo(25);
    expect(change(points, "higher")).toBeCloseTo(-25);
    expect(change(points, "neutral")).toBeNull();
    expect(change(points.slice(0, 1), "lower")).toBeNull();
  });

  it("draws one dot per measured session and breaks the reference where it is missing", () => {
    const line = series(inPeriod(list, "all", NOW), "base.adr");
    if (!line) throw new Error("no series");
    const g = geometry(line.points);
    expect(g.dots).toHaveLength(4);
    expect(g.bands).toHaveLength(4);
    expect(g.referenceLine.match(/M/g)).toHaveLength(2);
    expect(g.ticks.map((t) => t.value)).toEqual([70, 77, 84]);
    expect(g.dates.at(-1)?.index).toBe(3);
  });
});
