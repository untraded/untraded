// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { cache, Suspense } from "react";
import { MatchContext } from "@/components/match/match-context";
import { MatchPriorities } from "@/components/match/match-priorities";
import { MatchRounds } from "@/components/match/match-rounds";
import { PrioritiesSkeleton } from "@/components/match/match-skeletons";
import { MatchState } from "@/components/match/match-state";
import { RatingCard } from "@/components/match/rating-card";
import { SideSplit } from "@/components/match/side-split";
import { TeamTable } from "@/components/match/team-table";
import { Loading } from "@/components/skeleton";
import type { Locale } from "@/i18n/locale";
import {
  findPlayerMetrics,
  findRating,
  findSession,
  findSessionOf,
  getMatch,
  getMe,
  type MatchDetail,
} from "@/lib/api";
import { mapName, shortDay } from "@/lib/format";
import {
  type FlaggedMoment,
  flaggedRounds,
  minutes,
  prioritiesIn,
  roundsBySide,
} from "@/lib/match";
import { demoNote } from "@/lib/notes";

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const match = await getMatch((await params).id);
  return { title: match ? mapName(match.map) : "Untraded" };
}

/**
 * The match's session and its priorities that flag rounds of this match: the session is found in
 * the list of sessions, then its report read. Once per request, for the rounds and the priorities.
 */
const sessionOf = cache(async (matchId: string, playedAt: string | null) => {
  const summary = await findSessionOf(matchId, playedAt);
  const report = summary ? await findSession(summary.id) : null;
  return { summary, priorities: report ? prioritiesIn(report.advice, matchId) : [] };
});

/** No round flagged, while the session's report is on its way. */
const NONE = new Map<number, FlaggedMoment>();

/**
 * One match, seen from the player: the context bar (map, score, result, the player's rating),
 * then the rounds (each opens the 2D viewer), the rounds of this match that the session's
 * priorities flag, the player's rating and numbers on each side, then both teams. Before the
 * analysis ends, where it stands instead. The session's report is the slow part: the rounds are
 * sent without their frames and the priorities stream in when it comes.
 */
export default async function MatchPage({ params }: Params) {
  const id = (await params).id;
  const [me, match] = await Promise.all([getMe(), getMatch(id)]);
  if (!me || !match) redirect("/");
  const t = await getTranslations("match");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const ready = match.status === "ready";
  const played = match.players.some((p) => p.steam_id === me.steam_id);

  // The session (streamed) and the player's metrics are extras: the page stands without them.
  if (ready) void sessionOf(match.id, match.played_at);
  const [metrics, rating] =
    ready && played
      ? await Promise.all([
          findPlayerMetrics(match.id, me.steam_id),
          findRating(match.id, me.steam_id),
        ])
      : [null, null];
  const length = minutes(match.played_at, match.ended_at);
  const mine = match.my_team ?? "A";
  const theirs = mine === "A" ? "B" : "A";

  return (
    <>
      <MatchContext
        match={match}
        // From the rating detail only, as the rating panel the bar links to.
        rating={rating?.value ?? null}
        level={rating?.value == null ? null : (rating.level ?? null)}
        locale={locale}
        timeZone={timeZone}
      />
      <article className="flex flex-col gap-6">
        <div className="flex flex-wrap items-baseline gap-x-5 gap-y-2">
          <Link href="/matches" className="text-[0.8125rem] text-link underline underline-offset-3">
            {t("back")}
          </Link>
          {length !== null && (
            <p className="text-[0.8125rem] text-muted-foreground">
              {t("duration", { minutes: length })}
            </p>
          )}
          {match.unavailable.length > 0 && (
            <details className="basis-full text-xs text-muted-foreground">
              <summary className="cursor-pointer">
                {t("notes.title", { count: match.unavailable.length })}
              </summary>
              <ul className="mt-1 flex list-disc flex-col gap-0.5 pl-5">
                {match.unavailable.map((raw) => {
                  const note = demoNote(raw);
                  return (
                    <li key={raw}>
                      {note.kind === "other" ? (
                        <span translate="no" className="font-mono">
                          {note.text}
                        </span>
                      ) : note.kind === "surrender" ? (
                        t("notes.surrender", {
                          after: note.after,
                          loser: note.winner === "CT" ? "T" : "CT",
                          winner: note.winner,
                        })
                      ) : "count" in note ? (
                        t(`notes.${note.kind}`, { count: note.count })
                      ) : (
                        t(`notes.${note.kind}`)
                      )}
                    </li>
                  );
                })}
              </ul>
            </details>
          )}
        </div>

        {!ready && <MatchState match={match} />}

        {ready && match.rounds.length > 0 && (
          <Suspense fallback={<MatchRounds match={match} flagged={NONE} />}>
            <FlaggedRounds match={match} />
          </Suspense>
        )}

        {ready && (
          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <div className="flex min-w-0 flex-col gap-6">
              {played && (
                <Suspense
                  fallback={
                    <Loading announce={false}>
                      <PrioritiesSkeleton title={t("priorities")} />
                    </Loading>
                  }
                >
                  <Priorities match={match} locale={locale} timeZone={timeZone} />
                </Suspense>
              )}
              {played && <RatingCard rating={rating} locale={locale} />}
              {played && (
                <SideSplit
                  metrics={metrics?.metrics ?? null}
                  rounds={roundsBySide(match)}
                  locale={locale}
                />
              )}
            </div>
            <div className="flex min-w-0 flex-col gap-3.5">
              <TeamTable match={match} team={mine} me={me.steam_id} locale={locale} />
              <TeamTable match={match} team={theirs} me={me.steam_id} locale={locale} />
            </div>
          </div>
        )}
      </article>
    </>
  );
}

/** The rounds, those the session's priorities flag framed. */
async function FlaggedRounds({ match }: { match: MatchDetail }) {
  const { priorities } = await sessionOf(match.id, match.played_at);
  return <MatchRounds match={match} flagged={flaggedRounds(priorities)} />;
}

/** The session's priorities that flag rounds of this match, with a link to its report. */
async function Priorities({
  match,
  locale,
  timeZone,
}: {
  match: MatchDetail;
  locale: Locale;
  timeZone: string;
}) {
  const { summary, priorities } = await sessionOf(match.id, match.played_at);
  return (
    <MatchPriorities
      match={match}
      priorities={priorities}
      session={
        summary ? { id: summary.id, day: shortDay(summary.started_at, locale, timeZone) } : null
      }
    />
  );
}
