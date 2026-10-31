// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// Sending a demo, the parts that do not need a browser (tested): which files are demos, the
// date to suggest, what a refusal of `POST /uploads` means.

/** The demo files the API takes (`untraded.demofile`); FACEIT's are `.dem.zst`. */
export const DEMO_SUFFIXES = [".dem.bz2", ".dem.gz", ".dem.zst", ".dem"] as const;

/** What the file picker offers: `.dem.zst` files only show under their last extension. */
export const ACCEPT = ".dem,.bz2,.gz,.zst";

/** How long a match lasts, about: a demo file is written when the match ends. */
export const MATCH_MINUTES = 45;

export function isDemoName(name: string): boolean {
  const lower = name.toLowerCase();
  return DEMO_SUFFIXES.some((suffix) => lower.endsWith(suffix));
}

/** A FACEIT match id, as FACEIT names its demo files (`1-<uuid>-1-1.dem.zst`). */
const FACEIT_ID = /1-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

/** The FACEIT match a demo file comes from, read from its name; `null` when it says none. */
export function faceitMatchId(name: string): string | null {
  return FACEIT_ID.exec(name)?.[0].toLowerCase() ?? null;
}

/** When the match started, guessed from when its file was written, never in the future. */
export function guessPlayedAt(lastModified: number, now: number): Date {
  return new Date(Math.min(lastModified, now) - MATCH_MINUTES * 60_000);
}

/** A date as a `datetime-local` input shows it, in the browser's time zone. */
export function toLocalInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** A `datetime-local` value (the browser's time zone) as an instant the API takes; `null` when
 * empty or invalid. */
export function fromLocalInput(value: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

/** Why a send failed, as a message key: the API's reason, or what the status says. */
export type SendError =
  | "not_a_demo"
  | "too_large"
  | "consent"
  | "quota"
  | "busy"
  | "disk_full"
  | "off"
  | "date"
  | "network"
  | "unknown";

const REASONS = new Set<string>([
  "not_a_demo",
  "too_large",
  "consent",
  "quota",
  "busy",
  "disk_full",
]);

/** The failure of `POST /api/uploads`, from its status and body (`{detail: {reason}}`). */
export function sendError(status: number, body: string): SendError {
  let detail: unknown = null;
  try {
    detail = (JSON.parse(body) as { detail?: unknown }).detail;
  } catch {
    detail = null;
  }
  const { reason, field } = (detail ?? {}) as { reason?: unknown; field?: unknown };
  if (typeof reason === "string" && REASONS.has(reason)) return reason as SendError;
  if (field === "played_at") return "date";
  if (status === 413) return "too_large";
  if (status === 409) return "consent";
  if (status === 507) return "disk_full";
  if (status === 503) return "off";
  if (status === 0 || status === 502 || status === 504) return "network";
  return "unknown";
}
