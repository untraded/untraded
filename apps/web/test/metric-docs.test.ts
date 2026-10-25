// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import french from "../src/content/metric-docs.fr.json";
import {
  localize,
  type MetricDocsCatalog,
  parseMetricIndex,
  parseMetricPage,
  translatable,
  translate,
  translated,
} from "../src/lib/metric-docs";

// The real pages of the repository: when `just docs` changes them, these tests say what the site
// and its French words need.
const DIR = join(process.cwd(), "..", "..", "docs", "metrics");
const pages = readdirSync(DIR).filter(
  (f) => f.endsWith(".md") && f !== "README.md" && f !== "parameters.md",
);
const docs = pages.map((f) => parseMetricPage(readFileSync(join(DIR, f), "utf8")));
const index = parseMetricIndex(readFileSync(join(DIR, "README.md"), "utf8"));
const fr = french as MetricDocsCatalog;
const doc = (id: string) => {
  const found = docs.find((d) => d.id === id);
  if (!found) throw new Error(id);
  return found;
};

describe("metric docs", () => {
  it("reads every page and the index", () => {
    expect(docs.length).toBe(pages.length);
    expect(docs.length).toBeGreaterThan(70);
    expect(index.families.flatMap((f) => f.ids).sort()).toEqual(docs.map((d) => d.id).sort());
    expect(index.conventions.length).toBeGreaterThan(0);
    for (const d of docs) {
      expect(d.definition.length, d.id).toBeGreaterThan(0);
      expect(d.code?.url, d.id).toMatch(/^https:\/\/github\.com\/untraded\/untraded\//);
      expect(d.history[0]?.version, d.id).toBe("1.0.0");
    }
  });

  it("splits a page into its parts", () => {
    const rating = doc("rating.hltv1");
    expect(rating.name).toBe("HLTV Rating 1.0");
    expect(rating.family).toBe("rating");
    expect(rating.better).toBe("higher");
    expect(rating.reads).toEqual(["round_player"]);
    expect(rating.definition[0]).toMatch(/^\(KillRating/);
    expect(rating.example?.rows[0]).toContain("A1");
    const conversion = doc("trade.kill_conversion_pct");
    expect(conversion.params.map((p) => p.key)).toEqual([
      "trade.window_s",
      "trade.opportunity_distance",
    ]);
    const zones = doc("pos.death_zones");
    expect(zones.kind).toBe("table");
    expect(zones.example?.note).toMatch(/^First \d+ of \d+ rows\.$/);
  });

  it("has French words for every text, name and family, and none left over", () => {
    const texts = translatable(docs, index);
    expect(texts.filter((t) => !translated(t, fr))).toEqual([]);
    expect(Object.keys(fr.texts).filter((t) => !texts.includes(t))).toEqual([]);
    expect(docs.map((d) => d.id).filter((id) => !fr.names[id])).toEqual([]);
    expect(Object.keys(fr.names).filter((id) => !docs.some((d) => d.id === id))).toEqual([]);
    expect(index.families.map((f) => f.prefix).filter((p) => !fr.families[p])).toEqual([]);
  });

  it("translates by text, then by pattern, else keeps the English", () => {
    expect(translate("First version (#37).", fr)).toBe("Première version (#37).");
    expect(translate("First 8 of 40 rows.", fr)).toBe("Les 8 premières lignes sur 40.");
    expect(translate("1300.0 units", fr)).toBe("1300.0 unités");
    expect(translate("A sentence nobody wrote.", fr)).toBe("A sentence nobody wrote.");
    expect(translate("First version (#37).", null)).toBe("First version (#37).");
    const local = localize(doc("trade.untraded_deaths"), fr);
    expect(local.name).toBe("Morts non tradées (5 s)");
    expect(local.definition[0]).toMatch(/^Morts - morts tradées/);
  });
});
