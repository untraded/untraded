// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronRight, CircleSlash, Hourglass, type LucideIcon, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import type { Locale } from "@/i18n/locale";
import type { MatchStatus, TeamMatchSummary } from "@/lib/api";
import { cn } from "@/lib/cn";
import { mapName, shortDay, time, weekdayDay } from "@/lib/format";
import { isShared, teamScore } from "@/lib/team-matches";
import { teamMatchHref } from "@/lib/teams";

/** The columns of a row in a wide list (48rem and more, a container query: the team's home lists
 * them in a narrower column): when, map, score, mode, the team's players, chevron. Put the rows
 * and their heads in an `@container`. */
export const TEAM_MATCH_COLUMNS =
  "@3xl:grid-cols-[8.5rem_minmax(0,1fr)_6.5rem_4.5rem_minmax(0,1.5fr)_1rem] @3xl:items-center @3xl:gap-x-4";

/** A match not (yet) analysed says why with an icon beside the word. */
const WAITING: Record<Exclude<MatchStatus, "ready">, LucideIcon> = {
  pending: Hourglass,
  downloading: Hourglass,
  parsing: Hourglass,
  failed: TriangleAlert,
  unavailable: CircleSlash,
};

/** The column names, above a list of rows in a wide list (hidden from screen readers: each row
 * names its parts). */
export async function TeamMatchHeads() {
  const t = await getTranslations("matches");
  const tm = await getTranslations("teamMatches");
  return (
    <div
      aria-hidden="true"
      className={cn(
        "hidden border-b border-line-soft px-4 py-1.5 text-xs font-medium text-muted-foreground @3xl:grid",
        TEAM_MATCH_COLUMNS,
      )}
    >
      <span>{t("when")}</span>
      <span>{t("map")}</span>
      <span>{t("score")}</span>
      <span>{tm("mode")}</span>
      <span>{tm("players")}</span>
      <span />
    </div>
  );
}

/**
 * One of the team's matches, a link to its page on the team's pages: when, map, the score from
 * our side with the result (a letter and its word for screen readers, never the colour alone),
 * the mode and the team's players. A member's shared solo match, where the team has no side,
 * shows its score as it stands and says it is shared.
 */
export async function TeamMatchRow({
  slug,
  match,
  recent,
}: {
  slug: string;
  match: TeamMatchSummary;
  /** Played today or yesterday: the time alone says when (the group already says the day). */
  recent: boolean;
}) {
  const t = await getTranslations("teamMatches");
  const m = await getTranslations("match");
  const s = await getTranslations("sessions");
  const results = await getTranslations("result");
  const word = await getTranslations("status");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const at = match.played_at;
  const clock = time(at, locale, timeZone);
  const when = !at || recent ? clock : `${weekdayDay(at, locale, timeZone)}, ${clock}`;
  const whenShort = !at || recent ? clock : `${shortDay(at, locale, timeZone)}, ${clock}`;
  const score = teamScore(match);
  const result = match.our_result;
  const mode = `modes.${match.mode}`;
  const players = match.team_players.map((p) => p.name).join(", ");
  const Icon = match.status === "ready" ? null : WAITING[match.status];
  return (
    <li className="border-t border-line-soft first:border-t-0">
      <Link
        href={teamMatchHref(slug, match.id)}
        className={cn(
          "grid grid-cols-[minmax(0,1fr)_auto_1rem] gap-x-3 gap-y-1 px-3.5 py-2.5 hover:bg-muted @3xl:px-4 @3xl:py-2",
          TEAM_MATCH_COLUMNS,
        )}
      >
        <span className="col-start-1 row-start-2 text-xs whitespace-nowrap text-muted-foreground tabular-nums @3xl:row-start-1 @3xl:text-sm">
          <span className="@3xl:hidden">{whenShort}</span>
          <span className="hidden @3xl:inline">{when}</span>
        </span>
        <span className="col-start-1 row-start-1 truncate font-semibold @3xl:col-start-2">
          {mapName(match.map)}
        </span>
        {score ? (
          <span className="col-start-2 row-start-1 flex items-center justify-end gap-2 font-semibold tabular-nums @3xl:col-start-3 @3xl:justify-start">
            {result ? (
              <>
                <span
                  aria-hidden="true"
                  className={cn(
                    "grid size-5 place-items-center rounded-[3px] text-[0.6875rem] font-semibold",
                    result === "win" && "bg-win/15",
                    result === "loss" && "bg-loss/15",
                    result === "tie" && "bg-muted",
                  )}
                >
                  {s(`resultShort.${result}`)}
                </span>
                <span className="sr-only">{results(result)}</span>
              </>
            ) : (
              isShared(match) && (
                <span
                  title={t("sharedTitle")}
                  className="rounded-sm border border-border px-1.5 text-[0.6875rem] font-medium text-muted-foreground"
                >
                  {t("shared")}
                  <span className="sr-only"> ({t("sharedTitle")})</span>
                </span>
              )
            )}
            {score[0]} – {score[1]}
          </span>
        ) : (
          <span
            className={cn(
              "col-start-2 row-start-1 flex items-center justify-end gap-1.5 text-[0.8125rem] @3xl:col-start-3 @3xl:justify-start",
              match.status === "failed" ? "text-foreground" : "text-muted-foreground",
            )}
          >
            {Icon && <Icon aria-hidden="true" className="size-3.5 shrink-0" />}
            {word(match.status)}
          </span>
        )}
        <span className="col-start-2 row-start-2 text-right text-xs text-muted-foreground @3xl:col-start-4 @3xl:row-start-1 @3xl:text-left @3xl:text-sm">
          {m.has(mode) ? m(mode) : match.mode}
        </span>
        {players && (
          <span className="col-span-2 col-start-1 row-start-3 truncate text-xs text-muted-foreground @3xl:col-span-1 @3xl:col-start-5 @3xl:row-start-1 @3xl:text-sm">
            <span className="sr-only">{t("playersLabel")} </span>
            {players}
          </span>
        )}
        <ChevronRight
          aria-hidden="true"
          className={cn(
            "col-start-3 row-start-1 size-4 self-center text-muted-foreground @3xl:col-start-6 @3xl:row-span-1",
            players ? "row-span-3" : "row-span-2",
          )}
        />
      </Link>
    </li>
  );
}
