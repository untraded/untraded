// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { pickLocale } from "../src/i18n/locale";
import { killDiff, mapName, number, percent, score } from "../src/lib/format";

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
