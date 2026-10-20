// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// Display helpers, pure (tested without a browser).

import type { Locale } from "@/i18n/locale";
import type { PlayerLine } from "./api";

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
