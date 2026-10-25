// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The metric pages of the public repository (`docs/metrics/`, generated from the metric registry
// by `just docs`), read as they are: the formulas page shows them instead of a copy. The parser is
// pure (tested on every real page); reading the files is server-only.

/** A metric's page, in the words of the registry (English). */
export interface MetricDoc {
  id: string;
  name: string;
  /** The id's prefix: `base`, `duel`, `trade`... */
  family: string;
  version: string;
  /** `value` or `table`. */
  kind: string;
  unit: string;
  better: string;
  /** The canonical tables it reads. */
  reads: string[];
  code: { label: string; url: string } | null;
  /** Paragraphs, Markdown inline. */
  definition: string[];
  params: { key: string; value: string; meaning: string }[];
  /** Where the example comes from, then its table (head row first) and an optional note. */
  example: { where: string; rows: string[][]; note: string | null } | null;
  csdm: string;
  limits: string[];
  history: { version: string; text: string }[];
}

/** The index: the conventions every metric shares, and the families in their order. */
export interface MetricIndex {
  conventions: string[];
  families: { prefix: string; title: string; ids: string[] }[];
}

/** `## Title` sections of a page, and what comes before the first one. */
function sections(page: string): { head: string; parts: Map<string, string> } {
  const chunks = page.replace(/\r\n/g, "\n").split(/^## (.+)$/m);
  const parts = new Map<string, string>();
  for (let i = 1; i < chunks.length; i += 2)
    parts.set(chunks[i] ?? "", (chunks[i + 1] ?? "").trim());
  return { head: chunks[0] ?? "", parts };
}

/** The rows of the first Markdown table in a text (head row first, the separator dropped). */
function table(text: string): string[][] {
  const rows = text.split("\n").filter((line) => line.startsWith("|"));
  return rows
    .filter((_, i) => i !== 1)
    .map((line) =>
      line
        .replace(/^\||\|$/g, "")
        .split("|")
        .map((cell) => cell.trim()),
    );
}

/** The paragraphs of a text that are not a table, a list or a note in italics. */
function paragraphs(text: string): string[] {
  return text
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter((p) => p && !p.startsWith("|") && !p.startsWith("- "));
}

const items = (text: string) =>
  text
    .split("\n")
    .filter((line) => line.startsWith("- "))
    .map((line) => line.slice(2).trim());

/** One page of `docs/metrics/`. Throws when the page does not have the generated shape. */
export function parseMetricPage(page: string): MetricDoc {
  const { head, parts } = sections(page);
  const title = head.match(/^# `([^`]+)`: (.+)$/m);
  const meta = table(head)[1];
  if (!title?.[1] || !title[2] || !meta || meta.length < 6) {
    throw new Error("not a generated metric page");
  }
  const id = title[1];
  const [version = "", kind = "", unit = "", better = "", reads = "", code = ""] = meta;
  const link = code.match(/^\[(.+)\]\((https?:[^)]+)\)$/);
  const example = parts.get("Example");
  const exampleNote = example ? paragraphs(example).filter((p) => /^\*[^*].*\*$/.test(p)) : [];
  return {
    id,
    name: title[2],
    family: id.split(".")[0] ?? "",
    version,
    kind,
    unit,
    better,
    reads: [...reads.matchAll(/`([^`]+)`/g)].map((m) => m[1] ?? ""),
    code: link?.[1] && link[2] ? { label: link[1], url: link[2] } : null,
    definition: paragraphs(parts.get("Definition") ?? ""),
    params: table(parts.get("Parameters") ?? "")
      .slice(1)
      .map(([key = "", value = "", meaning = ""]) => ({
        key: key.replace(/`/g, ""),
        value,
        meaning,
      })),
    example: example
      ? {
          where: paragraphs(example)[0] ?? "",
          rows: table(example),
          note: exampleNote[0]?.slice(1, -1) ?? null,
        }
      : null,
    csdm: paragraphs(parts.get("Against CS Demo Manager") ?? "").join("\n\n"),
    limits: items(parts.get("Limits") ?? ""),
    history: items(parts.get("History") ?? "").map((line) => {
      const found = line.match(/^\*\*([^*]+)\*\*: (.*)$/);
      return found
        ? { version: found[1] ?? "", text: found[2] ?? "" }
        : { version: "", text: line };
    }),
  };
}

/** The index page (`README.md`): the shared conventions and the families, in order. */
export function parseMetricIndex(page: string): MetricIndex {
  const { parts } = sections(page);
  const conventions = items(parts.get("Shared conventions") ?? "");
  const families: MetricIndex["families"] = [];
  for (const [title, body] of parts) {
    if (title === "Shared conventions") continue;
    const ids = [...body.matchAll(/^\| \[`([^`]+)`\]/gm)].map((m) => m[1] ?? "");
    if (ids.length > 0) families.push({ prefix: ids[0]?.split(".")[0] ?? "", title, ids });
  }
  return { conventions, families };
}

/** Every text of the pages a reader can translate, once each: names aside, the words. */
export function translatable(docs: MetricDoc[], index: MetricIndex): string[] {
  const found = new Set<string>(index.conventions);
  for (const doc of docs) {
    for (const text of [
      ...doc.definition,
      ...doc.params.map((p) => p.meaning),
      doc.example?.where ?? "",
      doc.example?.note ?? "",
      doc.csdm,
      ...doc.limits,
      ...doc.history.map((h) => h.text),
    ]) {
      if (text) found.add(text);
    }
  }
  return [...found];
}

/** The French words of the pages (`src/content/metric-docs.fr.json`), by their English text. */
export interface MetricDocsCatalog {
  families: Record<string, string>;
  names: Record<string, string>;
  /** Sentences the generator repeats with a value in them: `[English regex, French with $1]`. */
  patterns: string[][];
  texts: Record<string, string>;
}

/** A text in the catalog's language: its translation, else a matching pattern, else as is. */
export function translate(text: string, catalog: MetricDocsCatalog | null): string {
  if (!catalog || !text) return text;
  const exact = catalog.texts[text];
  if (exact !== undefined) return exact;
  for (const [pattern = "", replacement = ""] of catalog.patterns) {
    const re = new RegExp(pattern);
    if (re.test(text)) return text.replace(re, replacement);
  }
  return text;
}

/** Whether a text has a translation (exact or by pattern). */
export function translated(text: string, catalog: MetricDocsCatalog): boolean {
  return (
    catalog.texts[text] !== undefined ||
    catalog.patterns.some(([p = ""]) => p !== "" && new RegExp(p).test(text))
  );
}

/** A page in the catalog's language; `null` keeps the registry's English. */
export function localize(doc: MetricDoc, catalog: MetricDocsCatalog | null): MetricDoc {
  if (!catalog) return doc;
  const t = (text: string) => translate(text, catalog);
  return {
    ...doc,
    name: catalog.names[doc.id] ?? doc.name,
    definition: doc.definition.map(t),
    params: doc.params.map((p) => ({ ...p, value: t(p.value), meaning: t(p.meaning) })),
    example: doc.example && {
      ...doc.example,
      where: t(doc.example.where),
      note: doc.example.note && t(doc.example.note),
    },
    csdm: t(doc.csdm),
    limits: doc.limits.map(t),
    history: doc.history.map((h) => ({ ...h, text: t(h.text) })),
  };
}
