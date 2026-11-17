// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// A team's matches on the site (`docs/contrat-api-equipes-e3.md` in the HQ): read from the team's
// side ("our side", `our_team`), where the player's own pages read from the player's.

import type { MatchDetail, TeamMatchDetail, TeamMatchSummary } from "./api";

/**
 * A team's match in the shape of the player's match page, its side the team's: the match page's
 * parts (context bar, rounds, state) then read "our side" where they read the player's. No line of
 * the player's own: the team's page is not the player's.
 */
export function asMatchDetail(match: TeamMatchDetail): MatchDetail {
  const { our_team, our_result, reason: _reason, team_players: _players, ...rest } = match;
  return {
    ...rest,
    my_team: our_team,
    my_result: our_result,
    my_line: null,
    players: match.players.map(({ member: _member, ...player }) => player),
  };
}

/** The score from our side (ours, then theirs), or as it stands (A, then B) when the team has no
 * side in the match; `null` before the match is parsed. */
export function teamScore(
  match: Pick<TeamMatchSummary, "status" | "score_a" | "score_b" | "our_team">,
): [number, number] | null {
  if (match.status !== "ready" || match.score_a === null || match.score_b === null) return null;
  return match.our_team === "B" ? [match.score_b, match.score_a] : [match.score_a, match.score_b];
}

/** A shared solo match: a member's own match, which the team sees without a side in it. */
export function isShared(match: Pick<TeamMatchSummary, "reason">): boolean {
  return match.reason === "shared";
}
