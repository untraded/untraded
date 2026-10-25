// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { pickLocale } from "../src/i18n/locale";
import { isTimeZone, pickTimeZone } from "../src/i18n/time-zone";
import {
  byPeriod,
  bytes,
  byWeek,
  compare,
  dateRange,
  day,
  delta,
  family,
  gap,
  gapPercent,
  gapTrend,
  hours,
  killDiff,
  localDate,
  mapName,
  metric,
  monday,
  number,
  percent,
  period,
  score,
  shortDay,
  time,
  trend,
  weekdayDay,
} from "../src/lib/format";

const line = { kills: 20, deaths: 14, adr: 81.4, kast: 72.2, hltv1: 1.18, untraded_deaths: 3 };

describe("format", () => {
  it("formats numbers per language, with a dash when undefined", () => {
    expect(number(1.184, "en", 2)).toBe("1.18");
    expect(number(1.184, "fr", 2)).toBe("1,18");
    expect(number(null, "en")).toBe("–");
    expect(number(Number.NaN, "en")).toBe("–");
    expect(percent(72.2, "en")).toBe("72 %");
  });

  it("signs the kill difference", () => {
    expect(killDiff(line)).toBe("+6");
    expect(killDiff({ ...line, kills: 10 })).toBe("-4");
    expect(killDiff(null)).toBe("–");
  });

  it("names maps and shows the score from the player's side", () => {
    expect(mapName("de_ancient")).toBe("Ancient");
    expect(mapName("cs_italy")).toBe("Italy");
    expect(score(4, 11, "A")).toBe("4 – 11");
    expect(score(4, 11, "B")).toBe("11 – 4");
    expect(score(null, 11, "A")).toBe("–");
  });
});

describe("pickLocale", () => {
  it("prefers the cookie, then the browser's best supported language", () => {
    expect(pickLocale("fr", "en-US,en;q=0.9")).toBe("fr");
    expect(pickLocale(undefined, "de-DE,fr;q=0.8,en;q=0.5")).toBe("fr");
    expect(pickLocale(undefined, "en;q=0.3,fr-FR;q=0.9")).toBe("fr");
    expect(pickLocale("xx", "de")).toBe("en");
    expect(pickLocale(undefined, null)).toBe("en");
  });
});

describe("metric values", () => {
  it("follows the unit, or two decimals per round", () => {
    expect(metric(54.36, "pct", "value", "en")).toBe("54.4 %");
    expect(metric(81.44, "damage_per_round", "value", "fr")).toBe("81,4");
    expect(metric(0.7354, "count", "per_round", "en")).toBe("0.74");
    expect(metric(1.5, "seconds", "value", "en")).toBe("1.50 s");
    expect(metric(null, "pct", "value", "en")).toBe("–");
  });

  it("signs differences, with no sign once rounded to zero", () => {
    expect(delta(3.21, "pct", "value", "en")).toBe("+3.2 %");
    expect(delta(-0.123, "count", "per_round", "fr")).toBe("−0,12");
    expect(delta(0.001, "ratio", "value", "en")).toBe("0.00");
  });

  it("groups metrics by family and writes days and ranges", () => {
    expect(family("trade.untraded_deaths")).toBe("trade");
    expect(day("2026-10-18", "en")).toBe("Oct 18, 2026");
    expect(dateRange("2026-10-19T18:00:00Z", "2026-10-19T19:30:00Z", "en", "UTC")).toMatch(/–/);
  });
});

describe("trend", () => {
  const base = {
    metric_id: "base.adr",
    version: "1.0.0",
    name: "ADR",
    unit: "damage_per_round",
    basis: "value" as const,
    session: 80,
    reference: 75,
    cases: null,
    signed: false,
  };
  it("reads the metric's direction", () => {
    expect(trend({ ...base, better: "higher", delta: 5 })).toBe("better");
    expect(trend({ ...base, better: "lower", delta: 5 })).toBe("worse");
    expect(trend({ ...base, better: "lower", delta: -5 })).toBe("better");
    expect(trend({ ...base, better: "neutral", delta: 5 })).toBe("same");
  });
  it("calls a difference that rounds to zero the same", () => {
    expect(trend({ ...base, better: "higher", delta: 0.04 })).toBe("same");
    expect(trend({ ...base, better: "higher", delta: null })).toBe("same");
  });
});

describe("gap", () => {
  const base = {
    metric_id: "base.adr",
    version: "1.0.0",
    name: "ADR",
    unit: "damage_per_round",
    basis: "value" as const,
    delta: null,
    cases: null,
    signed: false,
  };

  it("is a share of the reference, positive when better", () => {
    expect(gap({ ...base, better: "higher", session: 90, reference: 75 })).toBeCloseTo(20);
    expect(gap({ ...base, better: "lower", session: 0.3, reference: 0.25 })).toBeCloseTo(-20);
  });

  it("measures a negative reference by its size, so a better K-D stays positive", () => {
    // K-D of -2 against -4: two kills better, a 50 % improvement.
    expect(gap({ ...base, better: "higher", session: -2, reference: -4 })).toBeCloseTo(50);
    expect(gap({ ...base, better: "higher", session: -6, reference: -4 })).toBeCloseTo(-50);
  });

  it("is undefined without a session value", () => {
    expect(gap({ ...base, better: "higher", session: null, reference: 75 })).toBeNull();
  });

  it("is undefined without a reference, for a zero reference or a neutral metric", () => {
    expect(gap({ ...base, better: "higher", session: 90, reference: null })).toBeNull();
    expect(gap({ ...base, better: "higher", session: 90, reference: 0 })).toBeNull();
    expect(gap({ ...base, better: "neutral", session: 90, reference: 75 })).toBeNull();
  });

  it("reads small gaps as stable and signs whole percents", () => {
    expect(gapTrend(4.9)).toBe("same");
    expect(gapTrend(-5)).toBe("worse");
    expect(gapTrend(12)).toBe("better");
    expect(gapTrend(null)).toBe("same");
    expect(gapPercent(-24.4, "fr")).toBe("−24 %");
    expect(gapPercent(12.6, "en")).toBe("+13 %");
    expect(gapPercent(0.2, "en")).toBe("0 %");
  });
});

describe("compare", () => {
  const count = {
    metric_id: "base.multikills_4",
    version: "1.0.0",
    name: "4K",
    unit: "count",
    basis: "per_round" as const,
    better: "higher" as const,
    delta: null,
    cases: null,
    signed: false,
  };

  it("leaves out a count the reference expects fewer than 5 times this session", () => {
    // 0.1 per round over 39 rounds: about 4 expected.
    expect(compare({ ...count, session: 0.2, reference: 0.1 }, 39)).toEqual({
      kind: "rare",
      gap: null,
    });
  });

  it("ranks the same count once 5 events are expected", () => {
    // 0.13 per round over 39 rounds: about 5 expected.
    const result = compare({ ...count, session: 0.26, reference: 0.13 }, 39);
    expect(result.kind).toBe("ranked");
    expect(result.gap).toBeCloseTo(100);
  });

  it("leaves out a rate over fewer than 5 cases, and ranks it from 5", () => {
    const rate = {
      ...count,
      metric_id: "clutch.win_pct",
      unit: "pct",
      basis: "value" as const,
      session: 50,
      reference: 40,
    };
    expect(compare({ ...rate, cases: 2 }, 39)).toEqual({ kind: "few", gap: null });
    expect(compare({ ...rate, cases: 4 }, 39).kind).toBe("few");
    expect(compare({ ...rate, cases: 5 }, 39).kind).toBe("ranked");
    // A total has no cases: the count rule applies instead.
    expect(compare({ ...rate, cases: null }, 39).kind).toBe("ranked");
  });

  it("compares a signed metric (the K-D) in units, never as a share", () => {
    const kd = { ...count, metric_id: "base.kd_diff", signed: true, session: 0.2, reference: 0.01 };
    expect(compare(kd, 39)).toEqual({ kind: "units", gap: null });
  });

  it("tells neutral metrics apart from missing comparisons", () => {
    expect(compare({ ...count, better: "neutral", session: 1, reference: 1 }, 39).kind).toBe(
      "neutral",
    );
    expect(compare({ ...count, session: null, reference: 1 }, 39).kind).toBe("none");
    expect(
      compare({ ...count, unit: "pct", basis: "value", session: 50, reference: 0 }, 39).kind,
    ).toBe("none");
  });
});

describe("time zone", () => {
  // 22:30 UTC on 19 October is 00:30 on 20 October in Paris (summer time).
  const late = "2026-10-19T22:30:00Z";

  it("writes days and times in the given time zone, not the server's", () => {
    expect(shortDay(late, "fr", "Europe/Paris")).toBe("20 oct.");
    expect(shortDay(late, "fr", "UTC")).toBe("19 oct.");
    expect(time(late, "fr", "Europe/Paris")).toBe("00:30");
    expect(time(null, "fr", "Europe/Paris")).toBe("–");
    expect(dateRange(late, "2026-10-19T23:10:00Z", "fr", "Europe/Paris")).toMatch(
      /^20 oct\. 2026, 00:30/,
    );
  });

  it("keeps a valid cookie, else the instance's zone, else Paris", () => {
    expect(pickTimeZone("America/New_York", "UTC")).toBe("America/New_York");
    expect(pickTimeZone("Mars/Olympus", "Asia/Tokyo")).toBe("Asia/Tokyo");
    expect(pickTimeZone("Mars/Olympus", "nope")).toBe("Europe/Paris");
    expect(pickTimeZone(undefined, undefined)).toBe("Europe/Paris");
    expect(isTimeZone("Europe/Paris")).toBe(true);
    expect(isTimeZone("")).toBe(false);
  });
});

describe("bytes", () => {
  it("picks the largest unit above 1, in the player's language", () => {
    expect(bytes(412_000_000, "en")).toBe("412 MB");
    expect(bytes(21_500_000_000, "en")).toBe("21.5 GB");
    expect(bytes(512, "en")).toBe("512 byte");
    expect(bytes(null, "fr")).toBe("–");
    expect(bytes(400 * 1024 * 1024, "en", 1024)).toBe("400 MB");
  });
});

describe("weeks", () => {
  it("finds the Monday of a day, across months and years", () => {
    expect(monday("2026-10-21")).toBe("2026-10-19");
    expect(monday("2026-10-19")).toBe("2026-10-19");
    expect(monday("2026-10-25")).toBe("2026-10-19");
    expect(monday("2026-11-01")).toBe("2026-10-26");
    expect(monday("2027-01-02")).toBe("2026-12-28");
  });

  it("groups sessions by the week they start in, in the player's time zone", () => {
    // 22:30 UTC on Sunday 18 October is already Monday 19 in Paris.
    const sessions = [
      { id: "c", started_at: "2026-10-20T18:00:00Z" },
      { id: "b", started_at: "2026-10-18T22:30:00Z" },
      { id: "a", started_at: "2026-10-15T18:00:00Z" },
    ];
    expect(localDate(sessions[1]?.started_at ?? "", "Europe/Paris")).toBe("2026-10-19");
    const paris = byWeek(sessions, "Europe/Paris").map((w) => [w.monday, w.items.map((s) => s.id)]);
    expect(paris).toEqual([
      ["2026-10-19", ["c", "b"]],
      ["2026-10-12", ["a"]],
    ]);
    expect(byWeek(sessions, "UTC").map((w) => w.items.length)).toEqual([1, 2]);
  });

  it("writes the weekday and the hours, with the end's day when it changes", () => {
    expect(weekdayDay("2026-10-20T18:00:00Z", "fr", "Europe/Paris")).toBe("mar. 20 oct.");
    expect(weekdayDay("2026-10-20T18:00:00Z", "en", "Europe/Paris")).toBe("Tue, Oct 20");
    expect(hours("2026-10-20T15:00:00Z", "2026-10-20T19:38:00Z", "fr", "Europe/Paris")).toBe(
      "17:00 – 21:38",
    );
    expect(hours("2026-10-20T20:00:00Z", "2026-10-20T23:10:00Z", "fr", "Europe/Paris")).toBe(
      "22:00 – 21 oct. 01:10",
    );
  });

  it("groups matches by period, from today back to more than a month", () => {
    // Wednesday 21 October 2026, 10:00 in Paris; the week started on Monday 19.
    const now = "2026-10-21T08:00:00Z";
    const at = (iso: string | null) => period(iso, now, "Europe/Paris");
    expect(at("2026-10-20T22:30:00Z")).toBe("today"); // 00:30 on the 21st in Paris
    expect(at("2026-10-20T21:30:00Z")).toBe("yesterday");
    expect(at("2026-10-19T06:00:00Z")).toBe("thisWeek");
    expect(at("2026-10-18T20:00:00Z")).toBe("lastWeek");
    expect(at("2026-10-12T06:00:00Z")).toBe("lastWeek");
    expect(at("2026-10-11T20:00:00Z")).toBe("thisMonth");
    expect(at("2026-09-21T06:00:00Z")).toBe("thisMonth");
    expect(at("2026-09-20T06:00:00Z")).toBe("older");
    expect(at(null)).toBe("older");
    // On a Monday, yesterday is still "yesterday", not last week.
    expect(period("2026-10-18T10:00:00Z", "2026-10-19T10:00:00Z", "UTC")).toBe("yesterday");
    const groups = byPeriod(
      [
        { played_at: "2026-10-21T07:00:00Z" },
        { played_at: "2026-10-21T06:00:00Z" },
        { played_at: null },
      ],
      now,
      "Europe/Paris",
    );
    expect(groups.map((g) => [g.period, g.items.length])).toEqual([
      ["today", 2],
      ["older", 1],
    ]);
  });
});
