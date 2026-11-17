// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The filters of a team's Stats page (`/teams/[slug]/stats`), read from and written to its address.

import type { TeamMatchType } from "./api";
import { teamHref } from "./teams";

export type StatsQuery = { map?: string; days?: string; type?: string };

export const PERIODS = [7, 30, 90] as const;
export const TYPES: readonly TeamMatchType[] = ["all", "scrim", "official"];
const DEFAULT_DAYS = 30;

/** The filters of the address, as the API takes them: anything else falls back to the default. */
export function filtersOf(query: StatsQuery): {
  map: string | null;
  days: number;
  type: TeamMatchType;
} {
  const days = Number(query.days);
  const type = TYPES.find((t) => t === query.type) ?? "all";
  const map =
    typeof query.map === "string" && /^[a-z0-9_]{1,40}$/.test(query.map) ? query.map : null;
  return { map, days: (PERIODS as readonly number[]).includes(days) ? days : DEFAULT_DAYS, type };
}

/** The address of the page with some filters changed, the defaults left out. */
export function statsHref(
  slug: string,
  filters: { map: string | null; days: number; type: TeamMatchType },
): string {
  const query = new URLSearchParams();
  if (filters.map) query.set("map", filters.map);
  if (filters.days !== DEFAULT_DAYS) query.set("days", String(filters.days));
  if (filters.type !== "all") query.set("type", filters.type);
  const rest = query.toString();
  return `${teamHref(slug, "stats")}${rest ? `?${rest}` : ""}`;
}
