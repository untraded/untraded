// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Health } from "@/lib/api";

/**
 * A check's state on the admin's health page: fine, worth a look, failing, or not known. The page
 * says it with a word and an icon of its own shape, never the colour alone.
 */
export type CheckState = "ok" | "warn" | "fail" | "unknown";

/**
 * How old a daily run may be before it counts as late: the dump runs at 03:00 UTC and the off-site
 * copy at 04:00, so a day and a few hours of slack.
 */
export const LATE_HOURS = 30;
/** The share of the disk used past which it is worth a look, then failing. */
export const DISK_WARN = 0.8;
export const DISK_FAIL = 0.9;

const HOUR = 3_600_000;

function age(at: string, now: number): number | null {
  const time = Date.parse(at);
  return Number.isNaN(time) ? null : (now - time) / HOUR;
}

/** The last daily dump: none is failing, an old one is late. */
export function dumpState(backups: Health["backups"], now: number): CheckState {
  if (!backups.last) return "fail";
  const hours = age(backups.last.at, now);
  if (hours === null) return "unknown";
  return hours > LATE_HOURS ? "warn" : "ok";
}

/** What the off-site copy wrote in `offsite.json` (`{ok, at, message}`), read for the page. */
export interface Offsite {
  state: CheckState;
  /** When it last ran, if it said so. */
  at: string | null;
  /** Its own words, if any (a string it wrote, shown as text). */
  message: string | null;
  /** Its run is older than `LATE_HOURS`. */
  late: boolean;
}

/**
 * The off-site copy's state: none known is worth a look; `ok: false`, or a file that was not JSON,
 * is failing; a success older than `LATE_HOURS` is late; any other shape is not known.
 */
export function offsiteState(offsite: Health["backups"]["offsite"], now: number): Offsite {
  if (!offsite) return { state: "warn", at: null, message: null, late: false };
  // A date that does not parse is dropped: the page would fail to format it.
  const at = typeof offsite.at === "string" && age(offsite.at, now) !== null ? offsite.at : null;
  const message =
    typeof offsite.message === "string"
      ? offsite.message
      : typeof offsite.error === "string"
        ? offsite.error
        : null;
  const hours = at ? age(at, now) : null;
  const late = hours !== null && hours > LATE_HOURS;
  if (offsite.ok === false || typeof offsite.error === "string") {
    return { state: "fail", at, message, late };
  }
  if (offsite.ok !== true || hours === null) return { state: "unknown", at, message, late };
  return { state: late ? "warn" : "ok", at, message, late };
}

/** The disk the backups are on: its used share, and its state by `DISK_WARN` and `DISK_FAIL`. */
export function diskState(disk: Health["disk"]): { state: CheckState; used: number | null } {
  if (!disk || disk.total <= 0) return { state: "unknown", used: null };
  const used = Math.min(1, Math.max(0, (disk.total - disk.free) / disk.total));
  return { state: used >= DISK_FAIL ? "fail" : used >= DISK_WARN ? "warn" : "ok", used };
}

/** Jobs: any recent failure (dead, or waiting to retry after an error) is worth a look. */
export function jobsState(health: Health): CheckState {
  return health.failed_jobs.length > 0 ? "warn" : "ok";
}

/** Sources: any that errors is worth a look. */
export function sourcesState(sources: Health["sources"]): CheckState {
  return (sources.erroring ?? 0) > 0 ? "warn" : "ok";
}

/** The page's summary: the worst state, and how many checks are in it; a check not known is
 * worse than "all in order", which only holds when every check is fine. */
export function overall(states: CheckState[]): { state: CheckState; count: number } {
  for (const state of ["fail", "warn", "unknown"] as const) {
    const count = states.filter((s) => s === state).length;
    if (count > 0) return { state, count };
  }
  return { state: "ok", count: states.filter((s) => s === "ok").length };
}
