// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// Display helpers, pure (tested without a browser).

import type { Locale } from "@/i18n/locale";
import type { Comparison, PlayerLine } from "./api";

const DASH = "–";

/** A number with `digits` decimals in the user's language, or a dash when undefined. */
export function number(value: number | null | undefined, locale: Locale, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

/** KAST and other shares, stored as 0 to 100. */
export function percent(value: number | null | undefined, locale: Locale): string {
  return value === null || value === undefined ? DASH : `${number(value, locale, 0)} %`;
}

/** Kills minus deaths, signed. */
export function killDiff(line: PlayerLine | null): string {
  if (!line || line.kills === null || line.deaths === null) return DASH;
  const diff = Math.round(line.kills - line.deaths);
  return diff > 0 ? `+${diff}` : `${diff}`;
}

export function dateTime(iso: string | null, locale: Locale): string {
  if (!iso) return DASH;
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(iso),
  );
}

/** `de_mirage` → `Mirage`. */
export function mapName(map: string | null): string {
  if (!map) return DASH;
  const name = map.replace(/^(de|cs|ar)_/, "").replaceAll("_", " ");
  return name.charAt(0).toUpperCase() + name.slice(1);
}

/** The score seen from the player's team, when known. */
export function score(
  scoreA: number | null,
  scoreB: number | null,
  team: "A" | "B" | null,
): string {
  if (scoreA === null || scoreB === null) return DASH;
  return team === "B" ? `${scoreB} – ${scoreA}` : `${scoreA} – ${scoreB}`;
}

/** Decimals and suffix of a metric's values, from its unit and how it is compared. */
function style(unit: string, basis: Comparison["basis"]): { digits: number; suffix: string } {
  if (basis === "per_round") return { digits: 2, suffix: "" };
  switch (unit) {
    case "pct":
      return { digits: 1, suffix: " %" };
    case "damage_per_round":
      return { digits: 1, suffix: "" };
    case "seconds":
      return { digits: 2, suffix: " s" };
    case "dollars":
      return { digits: 0, suffix: " $" };
    case "units":
      return { digits: 0, suffix: "" };
    default:
      return { digits: 2, suffix: "" };
  }
}

/** A metric value, as its unit reads. */
export function metric(
  value: number | null,
  unit: string,
  basis: Comparison["basis"],
  locale: Locale,
): string {
  if (value === null || !Number.isFinite(value)) return DASH;
  const { digits, suffix } = style(unit, basis);
  return `${number(value, locale, digits)}${suffix}`;
}

/** A difference, always signed. */
export function delta(
  value: number | null,
  unit: string,
  basis: Comparison["basis"],
  locale: Locale,
): string {
  if (value === null || !Number.isFinite(value)) return DASH;
  const { digits } = style(unit, basis);
  const rounded = Number(value.toFixed(digits));
  const text = metric(Math.abs(value), unit, basis, locale);
  return rounded > 0 ? `+${text}` : rounded < 0 ? `−${text}` : text;
}

/** `base.adr` → `base`: the family a metric belongs to. */
export function family(metricId: string): string {
  return metricId.split(".")[0] ?? metricId;
}

export function dateRange(startIso: string, endIso: string, locale: Locale): string {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const day = new Intl.DateTimeFormat(locale, { dateStyle: "medium" });
  const time = new Intl.DateTimeFormat(locale, { timeStyle: "short" });
  return day.format(start) === day.format(end)
    ? `${day.format(start)}, ${time.format(start)} – ${time.format(end)}`
    : `${dateTime(startIso, locale)} – ${dateTime(endIso, locale)}`;
}

/** A calendar day (`2026-10-18`), as written in the user's language. */
export function day(isoDate: string, locale: Locale): string {
  const [year = 0, month = 1, date = 1] = isoDate.split("-").map(Number);
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: "UTC" }).format(
    new Date(Date.UTC(year, month - 1, date)),
  );
}

export type Trend = "better" | "worse" | "same";

/** Whether the session improves on the reference, once rounded as displayed. */
export function trend(comparison: Comparison): Trend {
  const { delta: value, better, unit, basis } = comparison;
  if (value === null || better === "neutral") return "same";
  const rounded = Number(value.toFixed(style(unit, basis).digits));
  if (rounded === 0) return "same";
  return rounded > 0 === (better === "higher") ? "better" : "worse";
}

/** Tailwind classes of a difference's colour. */
export function trendClass(t: Trend): string {
  return t === "better" ? "text-win" : t === "worse" ? "text-loss" : "text-muted-foreground";
}
