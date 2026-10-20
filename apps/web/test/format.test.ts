// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { pickLocale } from "../src/i18n/locale";
import {
  dateRange,
  day,
  delta,
  family,
  killDiff,
  mapName,
  metric,
  number,
  percent,
  score,
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
    expect(dateRange("2026-10-19T18:00:00Z", "2026-10-19T19:30:00Z", "en")).toMatch(/–/);
  });
});
