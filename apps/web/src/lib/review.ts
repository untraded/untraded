// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// A team's review on the site: comments on a round, tags and playlists of rounds
// (`docs/contrat-api-equipes-e7.md` in the HQ). The API checks every permission and limit; these
// helpers only shape what the pages send and link to.

import { teamHref, teamMatchHref } from "./teams";

/** The limits the API enforces, mirrored on the forms so that a player is stopped before. */
export const COMMENT_MAX = 2000;
export const TAG_MAX = 32;
export const TAGS_PER_ROUND = 10;
export const PLAYLIST_NAME_MAX = 80;
export const PLAYLIST_DESCRIPTION_MAX = 280;

/** The refusals a review page knows how to say; anything else reads as `failed`. */
export const REVIEW_ERRORS = [
  "forbidden",
  "read_only",
  "comment_invalid",
  "comment_limit",
  "tag_invalid",
  "tag_limit",
  "name_invalid",
  "description_invalid",
  "playlist_limit",
  "playlist_full",
  "order_invalid",
  "gone",
  "failed",
] as const;
export type ReviewError = (typeof REVIEW_ERRORS)[number];

/** The page's message for a refusal code the API sent (`refusalCode`), or for its status. */
export function reviewError(code: string | null, status: number): ReviewError {
  if (code === "demo") return "read_only";
  if (
    code === "match_not_found" ||
    code === "round_not_found" ||
    code === "comment_not_found" ||
    code === "playlist_not_found"
  ) {
    return "gone";
  }
  const known = REVIEW_ERRORS.find((e) => e === code);
  if (known) return known;
  return status === 403 ? "forbidden" : "failed";
}

/** A `?error=` value as the page reads it: one of `REVIEW_ERRORS`, else `failed`; none when absent. */
export function shownError(value: string | undefined): ReviewError | null {
  if (!value) return null;
  return REVIEW_ERRORS.find((e) => e === value) ?? "failed";
}

/**
 * The tags a player typed, comma separated: trimmed, blank space collapsed, empty ones dropped,
 * each once whatever its case (the first one written kept), as the API stores them.
 */
export function parseTags(input: string): string[] {
  const found: string[] = [];
  for (const raw of input.split(",")) {
    const tag = raw.trim().split(/\s+/).join(" ");
    if (tag && !found.some((t) => t.toLowerCase() === tag.toLowerCase())) found.push(tag);
  }
  return found;
}

/** A round number from an address (`?round=`), or `null`. */
export function roundParam(value: string | undefined): number | null {
  if (!value || !/^\d{1,2}$/.test(value)) return null;
  const round = Number(value);
  return round >= 1 && round <= 99 ? round : null;
}

/** The id of a round's block on the team's match page. */
export function roundAnchor(round: number): string {
  return `round-${round}`;
}

/** A round of a team's match, its review block open, on the team's match page. */
export function reviewRoundHref(slug: string, matchId: string, round: number): string {
  return `${teamMatchHref(slug, matchId)}?round=${round}#${roundAnchor(round)}`;
}

/** The 2D viewer on a round, at an instant of it when given. */
export function viewerHref(matchId: string, round: number, tick?: number | null): string {
  const base = `/matches/${encodeURIComponent(matchId)}/rounds/${round}`;
  return Number.isInteger(tick) && (tick as number) >= 0 ? `${base}?t=${tick}` : base;
}

/** The team's review page, on a playlist when given. */
export function reviewHref(slug: string, playlist?: string): string {
  const base = teamHref(slug, "review");
  return playlist ? `${base}?playlist=${encodeURIComponent(playlist)}` : base;
}

export interface RoundRef {
  match_id: string;
  round: number;
}

/** The playlist's order once the round at `index` moves by one place (`-1` up, `1` down); the
 * same order when it cannot move. */
export function moved<T extends RoundRef>(
  items: readonly T[],
  index: number,
  by: -1 | 1,
): RoundRef[] {
  const order = items.map(({ match_id, round }) => ({ match_id, round }));
  const target = index + by;
  if (index < 0 || index >= order.length || target < 0 || target >= order.length) return order;
  const [item] = order.splice(index, 1);
  if (item) order.splice(target, 0, item);
  return order;
}
