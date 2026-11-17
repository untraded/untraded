// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { RosterLists } from "@/components/teams/roster-lists";
import { TeamHeader } from "@/components/teams/team-header";
import { Panel } from "@/components/ui/panel";
import { getMe, getTeam } from "@/lib/api";
import { teamHref, validTeamParam } from "@/lib/teams";

type Params = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  if (!validTeamParam(slug)) return {};
  const team = await getTeam(slug);
  return team ? { title: team.name } : {};
}

/**
 * A team's home, minimal until its matches come (E3): its roster, and what is on the way. Members,
 * roles and invitations are on the members page.
 */
export default async function TeamHome({ params }: Params) {
  const { slug } = await params;
  if (!validTeamParam(slug)) notFound();
  const [me, t] = await Promise.all([getMe(), getTranslations("teams")]);
  if (!me) redirect("/");
  const team = await getTeam(slug);
  if (!team) redirect("/");
  return (
    <>
      <TeamHeader team={team} current="home" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] lg:items-start">
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
        <Panel title={t("soon")}>
          <p className="max-w-prose text-sm text-muted-foreground">{t("soonText")}</p>
        </Panel>
      </div>
    </>
  );
}
