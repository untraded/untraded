// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { MatchPriorities } from "@/components/match/match-priorities";
import { MatchRounds } from "@/components/match/match-rounds";
import { SideSplit } from "@/components/match/side-split";
import { TeamTable } from "@/components/match/team-table";
import { ResultBadge } from "@/components/result-badge";
import type { Locale } from "@/i18n/locale";
import { findPlayerMetrics, findSession, findSessionOf, getMatch, getMe } from "@/lib/api";
import { dateTime, mapName, shortDay } from "@/lib/format";
import { minutes, prioritiesIn, roundsBySide } from "@/lib/match";

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const match = await getMatch((await params).id);
  return { title: match ? mapName(match.map) : "Untraded" };
}

/**
 * One match, seen from the player: the rounds (each opens the 2D viewer), the rounds of this match
 * that the session's priorities flag, the player's numbers on each side, then both teams.
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

  // The session and the player's metrics are extras: the page stands without them.
  const [summary, metrics] = ready
    ? await Promise.all([
        findSessionOf(match.id, match.played_at),
        played ? findPlayerMetrics(match.id, me.steam_id) : null,
      ])
    : [null, null];
  const report = summary ? await findSession(summary.id) : null;
  const priorities = report ? prioritiesIn(report.advice, match.id) : [];
  const flagged = new Map<number, number>();
  for (const { rounds } of priorities) {
    for (const r of rounds) flagged.set(r.round, Math.min(flagged.get(r.round) ?? r.tick, r.tick));
  }
  const length = minutes(match.played_at, match.ended_at);
  const mode = `modes.${match.mode}`;
  const details = [
    t.has(mode) ? t(mode) : null,
    dateTime(match.played_at, locale, timeZone),
    length === null ? null : t("duration", { minutes: length }),
  ].filter(Boolean);
  const mine = match.my_team ?? "A";
  const theirs = mine === "A" ? "B" : "A";

  return (
    <article className="flex flex-col gap-7">
      <div className="flex flex-col gap-3">
        <Link
          href="/matches"
          className="self-start text-[0.8125rem] text-link underline underline-offset-3"
        >
          {t("back")}
        </Link>
        <header className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h1 className="text-2xl font-semibold">{mapName(match.map)}</h1>
          {match.score_a !== null && match.score_b !== null && (
            <p className="text-[1.75rem] leading-none font-semibold tabular-nums">
              {match.my_team === "B" ? match.score_b : match.score_a}
              <span className="px-0.5 text-muted-foreground">:</span>
              {match.my_team === "B" ? match.score_a : match.score_b}
            </p>
          )}
          <ResultBadge result={match.my_result} status={match.status} />
          <p className="text-[0.8125rem] text-muted-foreground">{details.join(" · ")}</p>
        </header>
        {!ready && <p className="text-muted-foreground">{match.error ?? t("notReady")}</p>}
        {match.unavailable.length > 0 && (
          <p className="text-xs text-muted-foreground">
            {t("missing", { items: match.unavailable.join(", ") })}
          </p>
        )}
      </div>

      {ready && match.rounds.length > 0 && <MatchRounds match={match} flagged={flagged} />}

      {ready && (
        <div className="grid items-start gap-7 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="flex min-w-0 flex-col gap-7">
            {played && (
              <MatchPriorities
                match={match}
                priorities={priorities}
                session={
                  summary
                    ? { id: summary.id, day: shortDay(summary.started_at, locale, timeZone) }
                    : null
                }
              />
            )}
            {played && (
              <SideSplit
                metrics={metrics?.metrics ?? null}
                rounds={roundsBySide(match)}
                locale={locale}
              />
            )}
          </div>
          <div className="flex min-w-0 flex-col gap-4">
            <TeamTable match={match} team={mine} me={me.steam_id} locale={locale} />
            <TeamTable match={match} team={theirs} me={me.steam_id} locale={locale} />
          </div>
        </div>
      )}
    </article>
  );
}
