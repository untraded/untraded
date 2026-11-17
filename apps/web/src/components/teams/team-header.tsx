// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { ContextBar } from "@/components/ui/context-bar";
import type { Team } from "@/lib/api";
import { readsMatches, teamHref } from "@/lib/teams";
import { roleLabel } from "./role-label";

/**
 * A team page's context bar, which holds its title: the team's name, its pages (the current one
 * marked by a filled tab with a rule under it and `aria-current`, not the colour alone), and at
 * the right the player's role and the team's size.
 */
export async function TeamHeader({
  team,
  current,
}: {
  team: Team;
  /** The page shown: a tab is marked only for the pages the bar lists. */
  current: "home" | "matches" | "stats" | "review" | "members" | "upload";
}) {
  const t = await getTranslations("teams");
  const tabs = [
    { key: "home", href: teamHref(team.slug), label: t("overview") },
    ...(readsMatches(team.my_role.permissions)
      ? [
          { key: "matches", href: teamHref(team.slug, "matches"), label: t("matches") },
          { key: "stats", href: teamHref(team.slug, "stats"), label: t("stats") },
          { key: "review", href: teamHref(team.slug, "review"), label: t("review") },
        ]
      : []),
    { key: "members", href: teamHref(team.slug, "members"), label: t("members") },
  ];
  return (
    <ContextBar label={t("context")}>
      <h1 className="min-w-0 text-lg leading-tight font-semibold break-words xl:shrink-0">
        {team.name}
      </h1>
      <nav aria-label={team.name} className="xl:shrink-0">
        <ul className="flex flex-wrap gap-1">
          {tabs.map((tab) => (
            <li key={tab.key}>
              <Link
                href={tab.href}
                aria-current={tab.key === current ? "page" : undefined}
                className="inline-flex h-7 items-center rounded-sm px-2.5 text-[0.8125rem] text-muted-foreground hover:bg-muted hover:text-foreground aria-[current=page]:bg-highlight-soft aria-[current=page]:font-semibold aria-[current=page]:text-foreground aria-[current=page]:shadow-[inset_0_-2px_0_var(--highlight)]"
              >
                {tab.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[0.8125rem] text-muted-foreground lg:ml-auto xl:shrink-0 xl:flex-nowrap">
        <span>{t("yourRole", { role: roleLabel(t, team.my_role.name) })}</span>
        <span className="tabular-nums">{t("membersCount", { count: team.members.length })}</span>
      </div>
    </ContextBar>
  );
}
