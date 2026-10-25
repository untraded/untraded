// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// Reads `docs/metrics/` from the repository (server only). In development the site runs from
// `apps/web`; in the container, the pages are traced next to the standalone server
// (`outputFileTracingIncludes` in `next.config.ts`) and it runs from the repository's root.

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import french from "@/content/metric-docs.fr.json";
import type { Locale } from "@/i18n/locale";
import {
  localize,
  type MetricDoc,
  type MetricDocsCatalog,
  type MetricIndex,
  parseMetricIndex,
  parseMetricPage,
  translate,
} from "./metric-docs";

const CANDIDATES = [join("docs", "metrics"), join("..", "..", "docs", "metrics")];

let cache: { docs: MetricDoc[]; index: MetricIndex } | null = null;

/** Every page and the index, in the registry's English, read once. */
export function metricDocs(): { docs: MetricDoc[]; index: MetricIndex } {
  if (cache) return cache;
  const dir = CANDIDATES.map((c) => join(process.cwd(), c)).find((d) =>
    existsSync(join(d, "README.md")),
  );
  if (!dir) throw new Error("docs/metrics not found");
  const docs = readdirSync(dir)
    .filter((f) => f.endsWith(".md") && f !== "README.md" && f !== "parameters.md")
    .map((f) => parseMetricPage(readFileSync(join(dir, f), "utf8")));
  cache = { docs, index: parseMetricIndex(readFileSync(join(dir, "README.md"), "utf8")) };
  return cache;
}

/** The catalog for a language: `null` for English, the pages' own language. */
export function catalogFor(locale: Locale): MetricDocsCatalog | null {
  return locale === "fr" ? (french as MetricDocsCatalog) : null;
}

/** One metric's page in a language, or `null` when there is no such metric. */
export function metricDoc(id: string, locale: Locale): MetricDoc | null {
  const doc = metricDocs().docs.find((d) => d.id === id);
  return doc ? localize(doc, catalogFor(locale)) : null;
}

/** The families, in order, with their pages and title in a language; the shared conventions. */
export function metricCatalog(locale: Locale): {
  conventions: string[];
  families: { prefix: string; title: string; docs: MetricDoc[] }[];
} {
  const { docs, index } = metricDocs();
  const catalog = catalogFor(locale);
  const byId = new Map(docs.map((d) => [d.id, localize(d, catalog)]));
  return {
    conventions: index.conventions.map((c) => translate(c, catalog)),
    families: index.families.map((f) => ({
      prefix: f.prefix,
      title: catalog?.families[f.prefix] ?? f.title,
      docs: f.ids.flatMap((id) => byId.get(id) ?? []),
    })),
  };
}
