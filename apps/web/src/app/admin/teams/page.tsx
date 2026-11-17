// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import { AdminHeader } from "@/components/admin/admin-header";
import { CreateTeamForm } from "@/components/admin/create-team-form";
import { Panel } from "@/components/ui/panel";
import type { Locale } from "@/i18n/locale";
import { adminOnlyMetadata } from "@/lib/admin-metadata";
import { getAdminTeams, getMe } from "@/lib/api";
import { day } from "@/lib/format";

export async function generateMetadata(): Promise<Metadata> {
  return adminOnlyMetadata(async () => (await getTranslations("admin"))("teams"));
}

/**
 * The teams, and creating one: during the beta an admin creates each team and names its owner,
 * who invites the others. Anyone who is not an admin gets the 404.
 */
export default async function AdminTeams() {
  const me = await getMe();
  if (!me) redirect("/");
  if (!me.admin) notFound();
  const [teams, t, teamsT, locale] = await Promise.all([
    getAdminTeams(),
    getTranslations("admin"),
    getTranslations("teams"),
    getLocale(),
  ]);
  const list = teams ?? [];
  return (
    <>
      <AdminHeader current="teams">
        <span className="tabular-nums">{t("teamsCount", { count: list.length })}</span>
      </AdminHeader>
      <div className="flex flex-col gap-4">
        <Panel title={t("createTeam")}>
          <CreateTeamForm
            labels={{
              name: t("teamName"),
              slug: t("teamSlug"),
              slugHelp: t("teamSlugHelp"),
              owner: t("teamOwner"),
              ownerHelp: t("teamOwnerHelp"),
              submit: t("create"),
              created: t("teamCreated", { name: "{name}" }),
              errors: {
                name: t("errorTeamName"),
                slug_invalid: teamsT("errors.slug_invalid"),
                slug_taken: teamsT("errors.slug_taken"),
                owner_format: t("errorSteamId"),
                owner_unknown: teamsT("errors.owner_unknown"),
                failed: teamsT("errors.failed"),
              },
            }}
          />
        </Panel>
        <Panel
          title={t("teams")}
          aside={<span className="tabular-nums">{t("teamsCount", { count: list.length })}</span>}
          flush
        >
          {list.length === 0 ? (
            <p className="px-3.5 py-3 text-sm text-muted-foreground">{t("noTeams")}</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line-soft text-left text-xs text-muted-foreground">
                  <th scope="col" className="px-3.5 py-1.5 font-medium">
                    {t("teamName")}
                  </th>
                  <th scope="col" className="px-3.5 py-1.5 font-medium max-sm:hidden">
                    {t("teamSlug")}
                  </th>
                  <th scope="col" className="px-3.5 py-1.5 text-right font-medium">
                    {t("teamMembers")}
                  </th>
                  <th scope="col" className="px-3.5 py-1.5 text-right font-medium">
                    {t("teamCreatedOn")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {list.map((team) => (
                  <tr key={team.id} className="border-t border-line-soft">
                    <td className="px-3.5 py-2.5 font-semibold break-words">{team.name}</td>
                    <td
                      className="px-3.5 py-2.5 font-mono text-xs text-muted-foreground max-sm:hidden"
                      translate="no"
                    >
                      {team.slug}
                    </td>
                    <td className="px-3.5 py-2.5 text-right tabular-nums">{team.members}</td>
                    <td className="px-3.5 py-2.5 text-right text-[0.8125rem] whitespace-nowrap text-muted-foreground">
                      {day(team.created_at.slice(0, 10), locale as Locale)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </>
  );
}
