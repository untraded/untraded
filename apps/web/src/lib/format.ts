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

export function dateTime(iso: string | null, locale: Locale, timeZone: string): string {
  if (!iso) return DASH;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  }).format(new Date(iso));
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

export function dateRange(
  startIso: string,
  endIso: string,
  locale: Locale,
  timeZone: string,
): string {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const day = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone });
  const time = new Intl.DateTimeFormat(locale, { timeStyle: "short", timeZone });
  return day.format(start) === day.format(end)
    ? `${day.format(start)}, ${time.format(start)} – ${time.format(end)}`
    : `${dateTime(startIso, locale, timeZone)} – ${dateTime(endIso, locale, timeZone)}`;
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

/** Below this share of the reference (in %), a gap reads as stable. */
export const STABLE_GAP = 5;

/**
 * How far the session is from the reference, in % of the reference, oriented so that a positive
 * gap is always an improvement (whatever way the metric runs). `null` when there is nothing to
 * compare, when the reference is zero, or for a neutral metric (no better way).
 */
export function gap(comparison: Comparison): number | null {
  const { session, reference, better } = comparison;
  if (session === null || reference === null || reference === 0 || better === "neutral") {
    return null;
  }
  const share = ((session - reference) / Math.abs(reference)) * 100;
  return better === "higher" ? share : -share;
}

/** The trend of an oriented gap, with a stable band around zero. */
export function gapTrend(value: number | null): Trend {
  if (value === null || Math.abs(value) < STABLE_GAP) return "same";
  return value > 0 ? "better" : "worse";
}

/** An oriented gap, signed, in whole percent: `+12 %`, `−24 %`. */
export function gapPercent(value: number | null, locale: Locale): string {
  if (value === null || !Number.isFinite(value)) return DASH;
  const rounded = Math.round(value);
  const text = `${number(Math.abs(rounded), locale)} %`;
  return rounded > 0 ? `+${text}` : rounded < 0 ? `−${text}` : text;
}

/** A day without the year, for titles: `20 oct.`, `Oct 20`. */
export function shortDay(iso: string, locale: Locale, timeZone: string): string {
  return new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", timeZone }).format(
    new Date(iso),
  );
}

/** A time of day: `23:00`, `11:00 PM`. */
export function time(iso: string | null, locale: Locale, timeZone: string): string {
  if (!iso) return DASH;
  return new Intl.DateTimeFormat(locale, { timeStyle: "short", timeZone }).format(new Date(iso));
}

/**
 * The one threshold of the metric list: a rate or an average over fewer cases (`cases`, from the
 * API), or a count the reference expects fewer times over the session's rounds, is not ranked.
 * This is a display rule; the advice engine has its own (`advice.min_events`).
 */
export const MIN_CASES = 5;

/** Below this many cases, a ranked rate still says what it stands on ("over 7 cases"). */
export const FEW_CASES = 10;

/**
 * How a metric compares to its reference in the list of every metric:
 * - `ranked`: as an oriented % gap, eligible for "what stands out";
 * - `units`: a signed metric, compared by its difference in units, never ranked;
 * - `few`: a rate or an average over fewer than `MIN_CASES` cases this session;
 * - `rare`: a count the reference expects fewer than `MIN_CASES` times this session;
 * - `neutral`: no better way; `none`: nothing to compare (no value or reference, or a zero one).
 */
export type GapKind = "ranked" | "units" | "few" | "rare" | "neutral" | "none";

export function compare(
  comparison: Comparison,
  rounds: number,
): { kind: GapKind; gap: number | null } {
  const { session, reference, better, unit, basis, cases } = comparison;
  if (better === "neutral") return { kind: "neutral", gap: null };
  if (session === null || reference === null) return { kind: "none", gap: null };
  if (comparison.signed) return { kind: "units", gap: null };
  if (cases !== null && cases < MIN_CASES) return { kind: "few", gap: null };
  if (unit === "count" && basis === "per_round" && Math.abs(reference) * rounds < MIN_CASES) {
    return { kind: "rare", gap: null };
  }
  const value = gap(comparison);
  return value === null ? { kind: "none", gap: null } : { kind: "ranked", gap: value };
}

/** A size in bytes, in the largest unit that keeps it above 1: `412 Mo`, `48 GB`. */
export function bytes(
  value: number | null | undefined,
  locale: Locale,
  /** 1024 for file sizes, as file managers and the upload limit (400 MB) count them. */
  base: 1000 | 1024 = 1000,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  const units = ["byte", "kilobyte", "megabyte", "gigabyte", "terabyte"] as const;
  let size = value;
  let unit = 0;
  while (size >= base && unit < units.length - 1) {
    size /= base;
    unit += 1;
  }
  return new Intl.NumberFormat(locale, {
    style: "unit",
    unit: units[unit],
    unitDisplay: "short",
    maximumFractionDigits: size < 100 && unit > 0 ? 1 : 0,
  }).format(size);
}

/** The calendar day of an instant in a time zone: `2026-10-20`. */
export function localDate(iso: string, timeZone: string): string {
  // `en-CA` writes dates as YYYY-MM-DD.
  return new Intl.DateTimeFormat("en-CA", { dateStyle: "short", timeZone }).format(new Date(iso));
}

/** The Monday of the week a calendar day belongs to (weeks run Monday to Sunday). */
export function monday(isoDate: string): string {
  const [year = 0, month = 1, date = 1] = isoDate.split("-").map(Number);
  const day = new Date(Date.UTC(year, month - 1, date));
  day.setUTCDate(day.getUTCDate() - ((day.getUTCDay() + 6) % 7));
  return day.toISOString().slice(0, 10);
}

/** Items grouped by the week they start in, in the user's time zone, keeping their order. */
export function byWeek<T extends { started_at: string }>(
  items: T[],
  timeZone: string,
): { monday: string; items: T[] }[] {
  const weeks: { monday: string; items: T[] }[] = [];
  for (const item of items) {
    const week = monday(localDate(item.started_at, timeZone));
    const last = weeks.at(-1);
    if (last?.monday === week) last.items.push(item);
    else weeks.push({ monday: week, items: [item] });
  }
  return weeks;
}

/** A day with its weekday, without the year: `mar. 20 oct.`, `Tue, Oct 20`. */
export function weekdayDay(iso: string, locale: Locale, timeZone: string): string {
  return new Intl.DateTimeFormat(locale, {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone,
  }).format(new Date(iso));
}

/** From one time to another, with the end's day when it falls on another one. */
export function hours(startIso: string, endIso: string, locale: Locale, timeZone: string): string {
  const end =
    localDate(startIso, timeZone) === localDate(endIso, timeZone)
      ? time(endIso, locale, timeZone)
      : `${shortDay(endIso, locale, timeZone)} ${time(endIso, locale, timeZone)}`;
  return `${time(startIso, locale, timeZone)} – ${end}`;
}

/** How far back the list of matches groups: the first period that holds a match wins. */
export const PERIODS = [
  "today",
  "yesterday",
  "thisWeek",
  "lastWeek",
  "thisMonth",
  "older",
] as const;
export type Period = (typeof PERIODS)[number];

/** A calendar day `days` before another one: `2026-10-20`, 1 → `2026-10-19`. */
function daysBefore(isoDate: string, days: number): string {
  return new Date(Date.parse(`${isoDate}T00:00:00Z`) - days * 86_400_000)
    .toISOString()
    .slice(0, 10);
}

/**
 * Which period an instant falls in, seen from `now` in the user's time zone: today, yesterday,
 * this week and last week (Monday to Sunday), the last 30 days, then older. An unknown date is
 * older.
 */
export function period(iso: string | null, now: string, timeZone: string): Period {
  if (!iso) return "older";
  const day = localDate(iso, timeZone);
  const today = localDate(now, timeZone);
  const week = monday(today);
  if (day >= today) return "today";
  if (day === daysBefore(today, 1)) return "yesterday";
  if (day >= week) return "thisWeek";
  if (day >= daysBefore(week, 7)) return "lastWeek";
  if (day >= daysBefore(today, 30)) return "thisMonth";
  return "older";
}

/** Items grouped by period, newest first as given, keeping their order. */
export function byPeriod<T extends { played_at: string | null }>(
  items: T[],
  now: string,
  timeZone: string,
): { period: Period; items: T[] }[] {
  const groups: { period: Period; items: T[] }[] = [];
  for (const item of items) {
    const found = period(item.played_at, now, timeZone);
    const last = groups.at(-1);
    if (last?.period === found) last.items.push(item);
    else groups.push({ period: found, items: [item] });
  }
  return groups;
}
