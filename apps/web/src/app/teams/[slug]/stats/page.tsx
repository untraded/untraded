// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { MIN_ROUNDS, TeamStatsView } from "@/components/teams/team-stats-view";
import { getMe, getTeam, getTeamStats } from "@/lib/api";
import { mapName } from "@/lib/format";
import { filtersOf, PERIODS, type StatsQuery, statsHref, TYPES } from "@/lib/team-stats";
import { readsMatches, validTeamParam } from "@/lib/teams";

type Params = { params: Promise<{ slug: string }>; searchParams: Promise<StatsQuery> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  if (!validTeamParam(slug)) return {};
  const [team, t] = await Promise.all([getTeam(slug), getTranslations("teams")]);
  return team ? { title: `${t("stats")} · ${team.name}` } : {};
}

const CHIP =
  "inline-flex h-7 items-center rounded-sm border border-border px-2.5 text-[0.8125rem] text-muted-foreground hover:bg-muted hover:text-foreground aria-[current=true]:border-highlight aria-[current=true]:bg-highlight-soft aria-[current=true]:font-semibold aria-[current=true]:text-foreground";

/** One filter: a label and its choices as links, the current one marked by `aria-current` and a
 * filled, bordered chip (not the colour alone). */
function Filter({
  label,
  choices,
}: {
  label: string;
  choices: { key: string; label: string; href: string; current: boolean }[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="mr-1 text-xs text-muted-foreground">{label}</span>
      <ul className="flex flex-wrap gap-1">
        {choices.map((c) => (
          <li key={c.key}>
            <Link href={c.href} aria-current={c.current ? "true" : undefined} className={CHIP}>
              {c.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * A team's tactical numbers over its matches: where it wins on T, its post-plants and retakes,
 * its economy, and who trades whom. Filters by map, period and type are links, so the page works
 * without script and an address can be shared. A role that does not read the team's matches gets
 * the 404 page, as the API would refuse it.
 */
export default async function TeamStatsPage({ params, searchParams }: Params) {
  const { slug } = await params;
  if (!validTeamParam(slug)) notFound();
  const filters = filtersOf(await searchParams);
  const [me, team] = await Promise.all([getMe(), getTeam(slug)]);
  if (!me || !team) redirect("/");
  if (!readsMatches(team.my_role.permissions)) notFound();
  const stats = await getTeamStats(team.slug, filters);
  if (!stats) redirect("/");
  const [t, teamsT] = await Promise.all([getTranslations("teamStats"), getTranslations("teams")]);
  // The map chosen stays a choice even when the period has none of its matches.
  const maps =
    filters.map && !stats.maps.includes(filters.map) ? [...stats.maps, filters.map] : stats.maps;
  return (
    <>
      <h1 className="mb-5 text-2xl font-semibold break-words md:text-[1.75rem]">
        {teamsT("stats")}
      </h1>
      <section className="flex flex-col gap-4" aria-label={teamsT("stats")}>
        <p className="max-w-prose text-sm text-muted-foreground">
          {t("pageLead", { min: MIN_ROUNDS })}
        </p>
        <nav aria-label={t("filters")} className="flex flex-col gap-2">
          <Filter
            label={t("period")}
            choices={PERIODS.map((days) => ({
              key: String(days),
              label: t("days", { days }),
              href: statsHref(team.slug, { ...filters, days }),
              current: filters.days === days,
            }))}
          />
          <Filter
            label={t("type")}
            choices={TYPES.map((type) => ({
              key: type,
              label: t(`types.${type}`),
              href: statsHref(team.slug, { ...filters, type }),
              current: filters.type === type,
            }))}
          />
          {maps.length > 0 && (
            <Filter
              label={t("map")}
              choices={[
                {
                  key: "all",
                  label: t("allMaps"),
                  href: statsHref(team.slug, { ...filters, map: null }),
                  current: filters.map === null,
                },
                ...maps.map((map) => ({
                  key: map,
                  label: mapName(map),
                  href: statsHref(team.slug, { ...filters, map }),
                  current: filters.map === map,
                })),
              ]}
            />
          )}
        </nav>
        {(stats.matches > 0 || stats.pending > 0) && (
          <p className="text-sm tabular-nums">
            {stats.matches > 0 && t("summary", { matches: stats.matches, rounds: stats.rounds })}
            {stats.pending > 0 && (
              <span className="block text-xs text-muted-foreground">
                {t("pending", { count: stats.pending })}
              </span>
            )}
          </p>
        )}
        {stats.matches === 0 && stats.pending > 0 ? null : stats.matches === 0 ? (
          <p className="max-w-prose rounded-lg border border-dashed border-border px-3.5 py-3 text-sm text-muted-foreground">
            {t("empty")}
          </p>
        ) : (
          <TeamStatsView stats={stats} />
        )}
      </section>
    </>
  );
}
