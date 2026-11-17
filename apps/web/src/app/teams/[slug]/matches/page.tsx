// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTimeZone, getTranslations } from "next-intl/server";
import { TeamMatchHeads, TeamMatchRow } from "@/components/teams/team-match-row";
import { buttonVariants } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { getMe, getTeam, getTeamMatches, TEAM_MATCH_PAGE } from "@/lib/api";
import { cn } from "@/lib/cn";
import { byPeriod } from "@/lib/format";
import { readsMatches, teamHref, validTeamParam } from "@/lib/teams";

type Params = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ offset?: string }>;
};

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  if (!validTeamParam(slug)) return {};
  const [team, t] = await Promise.all([getTeam(slug), getTranslations("teams")]);
  return team ? { title: `${t("matches")} · ${team.name}` } : {};
}

/**
 * The matches a team sees, newest first, grouped by period as the player's own list: one panel
 * per period, its record from our side in the band. Each row opens the match on the team's pages.
 * A role that does not read the team's matches gets the 404 page, as the API would refuse it.
 */
export default async function TeamMatches({ params, searchParams }: Params) {
  const { slug } = await params;
  if (!validTeamParam(slug)) notFound();
  const asked = Math.trunc(Number((await searchParams).offset ?? 0));
  const offset = Number.isSafeInteger(asked) && asked > 0 ? asked : 0;
  const [me, team] = await Promise.all([getMe(), getTeam(slug)]);
  if (!me || !team) redirect("/");
  if (!readsMatches(team.my_role.permissions)) notFound();
  const list = await getTeamMatches(team.slug, offset);
  if (!list) redirect("/");
  const [t, tm, teamsT, s, timeZone] = await Promise.all([
    getTranslations("matches"),
    getTranslations("teamMatches"),
    getTranslations("teams"),
    getTranslations("sessions"),
    getTimeZone(),
  ]);
  const now = new Date().toISOString();
  const base = teamHref(team.slug, "matches");
  const pager = "h-8 gap-1.5 text-[0.8125rem]";
  return (
    <>
      <h1 className="mb-5 text-2xl font-semibold break-words md:text-[1.75rem]">
        {teamsT("matches")}
      </h1>
      <section className="flex flex-col gap-4" aria-label={teamsT("matches")}>
        <p className="max-w-prose text-sm text-muted-foreground">{tm("pageLead")}</p>
        {list.items.length === 0 && (
          <p className="max-w-prose text-muted-foreground">
            {offset > 0 ? tm("noMore") : teamsT("noMatches")}
          </p>
        )}
        {byPeriod(list.items, now, timeZone).map((group) => {
          const count = (result: "win" | "loss" | "tie") =>
            group.items.filter((m) => m.our_result === result).length;
          const recent = group.period === "today" || group.period === "yesterday";
          return (
            <Panel
              key={group.items[0]?.id ?? group.period}
              title={t(`periods.${group.period}`)}
              aside={
                <span className="tabular-nums">
                  {t("periodSummary", {
                    matches: group.items.length,
                    record: s("record", {
                      wins: count("win"),
                      losses: count("loss"),
                      ties: count("tie"),
                    }),
                  })}
                </span>
              }
              flush
            >
              <div className="@container">
                <TeamMatchHeads />
                <ul>
                  {group.items.map((match) => (
                    <TeamMatchRow key={match.id} slug={team.slug} match={match} recent={recent} />
                  ))}
                </ul>
              </div>
            </Panel>
          );
        })}
        {(offset > 0 || list.items.length === TEAM_MATCH_PAGE) && (
          <nav aria-label={tm("pages")} className="flex items-center justify-between gap-3">
            {offset > 0 ? (
              <Link
                href={`${base}?offset=${Math.max(0, offset - TEAM_MATCH_PAGE)}`}
                className={cn(buttonVariants({ variant: "outline" }), pager)}
              >
                <ChevronLeft aria-hidden="true" className="size-4" />
                {t("newer")}
              </Link>
            ) : (
              <span />
            )}
            <span className="text-[0.8125rem] text-muted-foreground">
              {t("pageOf", { from: offset + 1, to: offset + list.items.length })}
            </span>
            {list.items.length === TEAM_MATCH_PAGE ? (
              <Link
                href={`${base}?offset=${offset + TEAM_MATCH_PAGE}`}
                className={cn(buttonVariants({ variant: "outline" }), pager)}
              >
                {t("older")}
                <ChevronRight aria-hidden="true" className="size-4" />
              </Link>
            ) : (
              <span />
            )}
          </nav>
        )}
      </section>
    </>
  );
}
