// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { RosterLists } from "@/components/teams/roster-lists";
import { TeamMatchRow } from "@/components/teams/team-match-row";
import { Panel } from "@/components/ui/panel";
import { findTeamOverview, getMe, getTeam, type Team, type TeamOverview } from "@/lib/api";
import { readsMatches, teamHref, validTeamParam } from "@/lib/teams";

type Params = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  if (!validTeamParam(slug)) return {};
  const team = await getTeam(slug);
  return team ? { title: team.name } : {};
}

/**
 * A team's home: its roster, and beside it its latest matches with its record over the last 30
 * days, from our side. Members, roles and invitations are on the members page; every match is on
 * the matches page.
 */
export default async function TeamHome({ params }: Params) {
  const { slug } = await params;
  if (!validTeamParam(slug)) notFound();
  const [me, t] = await Promise.all([getMe(), getTranslations("teams")]);
  if (!me) redirect("/");
  const team = await getTeam(slug);
  if (!team) redirect("/");
  // The matches' panel, for a role that reads them; the page stands without it.
  const overview = readsMatches(team.my_role.permissions)
    ? await findTeamOverview(team.slug)
    : null;
  return (
    <>
      <h1 className="mb-5 text-2xl font-semibold break-words md:text-[1.75rem]">{team.name}</h1>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] lg:items-start">
        {overview && <Recent team={team} overview={overview} />}
        <Panel
          title={t("roster")}
          aside={
            <Link
              href={teamHref(team.slug, "members")}
              className="underline decoration-muted-foreground underline-offset-3 hover:text-foreground hover:decoration-foreground"
            >
              {t("members")}
            </Link>
          }
          flush
        >
          <RosterLists team={team} meSteamId={me.steam_id} />
        </Panel>
      </div>
    </>
  );
}

/**
 * The team's latest matches, the record of the last 30 days in the band (matches whose side is
 * known), and a link to every match.
 */
async function Recent({ team, overview }: { team: Team; overview: TeamOverview }) {
  const [t, s] = await Promise.all([getTranslations("teams"), getTranslations("sessions")]);
  const { record } = overview;
  const counted = record.wins + record.losses + record.ties;
  return (
    <Panel
      title={t("recent")}
      aside={
        <span className="tabular-nums">
          {t("recordDays", { days: record.days })}
          {counted > 0 && (
            <>
              {" · "}
              {s("record", { wins: record.wins, losses: record.losses, ties: record.ties })}
            </>
          )}
        </span>
      }
      flush
    >
      {overview.recent.length === 0 ? (
        <p className="max-w-prose px-4 py-3 text-sm text-muted-foreground">{t("noMatches")}</p>
      ) : (
        <>
          <ul className="@container">
            {overview.recent.map((match) => (
              <TeamMatchRow key={match.id} slug={team.slug} match={match} recent={false} />
            ))}
          </ul>
          <p className="border-t border-line-soft px-4 py-2.5 text-[0.8125rem]">
            <Link
              href={teamHref(team.slug, "matches")}
              className="underline decoration-muted-foreground underline-offset-3 hover:decoration-foreground"
            >
              {t("allMatches", { count: overview.matches })}
            </Link>
          </p>
          {counted === 0 && (
            <p className="px-4 pb-3 text-xs text-muted-foreground">
              {t("recordNone", { days: record.days })}
            </p>
          )}
        </>
      )}
    </Panel>
  );
}
