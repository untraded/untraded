// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { MatchContext } from "@/components/match/match-context";
import { MatchRounds } from "@/components/match/match-rounds";
import { MatchState } from "@/components/match/match-state";
import { TeamTable } from "@/components/match/team-table";
import { RoundReview } from "@/components/teams/round-review";
import type { Locale } from "@/i18n/locale";
import { findMatchReview, getMe, getTeam, getTeamMatch } from "@/lib/api";
import { mapName } from "@/lib/format";
import { type FlaggedMoment, minutes } from "@/lib/match";
import { roundParam, shownError } from "@/lib/review";
import { asMatchDetail, isShared } from "@/lib/team-matches";
import { readsMatches, teamHref, teamMatchHref, validTeamParam } from "@/lib/teams";

type Params = {
  params: Promise<{ slug: string; id: string }>;
  searchParams?: Promise<{ round?: string; error?: string }>;
};

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug, id } = await params;
  if (!validTeamParam(slug) || !UUID.test(id)) return {};
  const team = await getTeam(slug);
  if (!team || !readsMatches(team.my_role.permissions)) return {};
  const match = await getTeamMatch(team.slug, id);
  return match ? { title: `${mapName(match.map)} · ${team.name}` } : {};
}

/** A match id, as the API gives them: anything else is a page that does not exist. */
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** No round flagged: the priorities are a player's, never a team's. */
const NONE = new Map<number, FlaggedMoment>();

/**
 * One of the team's matches, read from our side: the context bar (map, score and result from our
 * side), then the rounds (each opens the 2D viewer) and both teams, ours first. Nothing of a
 * player's coaching (sessions, priorities, the player's own figures against their previous
 * matches): a team sees matches, not coaching. A member's shared solo match, where the team has no
 * side, reads as the match stands (team A, then team B). Before the analysis ends, where it stands
 * instead. Once parsed, the team's review of it, round by round (`?round=` opens one, as the review
 * forms come back to it).
 */
export default async function TeamMatchPage({ params, searchParams }: Params) {
  const { slug, id } = await params;
  const query = (await searchParams) ?? {};
  if (!validTeamParam(slug) || !UUID.test(id)) notFound();
  const [me, team] = await Promise.all([getMe(), getTeam(slug)]);
  if (!me || !team) redirect("/");
  if (!readsMatches(team.my_role.permissions)) notFound();
  const found = await getTeamMatch(team.slug, id);
  if (!found) redirect("/");
  const match = asMatchDetail(found);
  const ready = match.status === "ready";
  const [t, tm, timeZone, review] = await Promise.all([
    getTranslations("match"),
    getTranslations("teamMatches"),
    getTimeZone(),
    ready && match.rounds.length > 0 ? findMatchReview(team.slug, match.id) : null,
  ]);
  const locale = (await getLocale()) as Locale;
  const length = minutes(match.played_at, match.ended_at);
  const ours = match.my_team ?? "A";
  const theirs = ours === "A" ? "B" : "A";
  return (
    <>
      <MatchContext match={match} rating={null} level={null} locale={locale} timeZone={timeZone} />
      <article className="flex flex-col gap-6" aria-label={team.name}>
        <div className="flex flex-wrap items-baseline gap-x-5 gap-y-2">
          <Link
            href={teamHref(team.slug, "matches")}
            className="text-[0.8125rem] text-link underline underline-offset-3"
          >
            {tm("back")}
          </Link>
          {length !== null && (
            <p className="text-[0.8125rem] text-muted-foreground">
              {t("duration", { minutes: length })}
            </p>
          )}
          {found.our_team === null && (
            <p className="text-[0.8125rem] text-muted-foreground">
              {isShared(found) ? tm("sharedTitle") : tm("noSide")}
            </p>
          )}
        </div>

        {!ready && (
          <MatchState match={match} href={teamMatchHref(team.slug, match.id)} ours="team" />
        )}

        {ready && match.rounds.length > 0 && (
          <MatchRounds match={match} flagged={NONE} ours="team" />
        )}

        {ready && (
          <div className="grid items-start gap-3.5 lg:grid-cols-2">
            <TeamTable match={match} team={ours} me={me.steam_id} locale={locale} ours="team" />
            <TeamTable match={match} team={theirs} me={me.steam_id} locale={locale} ours="team" />
          </div>
        )}

        {ready && match.rounds.length > 0 && (
          <RoundReview
            slug={team.slug}
            match={match}
            review={review}
            open={roundParam(query.round)}
            error={shownError(query.error)}
            readOnly={me.demo === true}
            locale={locale}
            timeZone={timeZone}
          />
        )}
      </article>
    </>
  );
}
