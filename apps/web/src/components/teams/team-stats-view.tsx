// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getLocale, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { Panel } from "@/components/ui/panel";
import type { Locale } from "@/i18n/locale";
import type { RoundCount, TeamPlantBlock, TeamStats } from "@/lib/api";
import { mapName, number } from "@/lib/format";

/** Below this many rounds a rate is shown, but neither drawn as a bar nor tinted: a team's
 * samples are small, and 3 of 4 says little. */
export const MIN_ROUNDS = 10;

/** The rate of a count, 0 to 1; null without a round. */
export function rate(count: RoundCount): number | null {
  return count.rounds > 0 ? count.won / count.rounds : null;
}

function percentOf(value: number | null, locale: Locale): string {
  return value === null ? "–" : `${number(value * 100, locale)} %`;
}

/**
 * One line of a success table: a name, "won of rounds", a bar of the rate, the rate. A rate on
 * fewer than `MIN_ROUNDS` rounds keeps its numbers but loses its bar, and says so in words: never
 * the colour alone.
 */
async function RateRow({ name, count }: { name: ReactNode; count: RoundCount }) {
  const [t, locale] = await Promise.all([
    getTranslations("teamStats"),
    getLocale() as Promise<Locale>,
  ]);
  const value = rate(count);
  const enough = count.rounds >= MIN_ROUNDS;
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto_3rem] items-center gap-x-3 border-t border-line-soft py-1.5 text-sm first:border-t-0 sm:grid-cols-[minmax(5.5rem,1fr)_auto_minmax(2.5rem,1fr)_3rem]">
      <span className="min-w-0 truncate">{name}</span>
      <span className="text-right text-xs text-muted-foreground tabular-nums">
        {t("won", { won: count.won, rounds: count.rounds })}
        {!enough && count.rounds > 0 && <span className="block">{t("few")}</span>}
      </span>
      {/* Too few rounds: no track either, which would read as 0 %. */}
      <span aria-hidden="true" className="hidden sm:block">
        {enough && value !== null && (
          <span className="block h-2 overflow-hidden rounded-full bg-muted">
            <span
              className="block h-full rounded-full bg-foreground/70"
              style={{ width: `${value * 100}%` }}
            />
          </span>
        )}
      </span>
      <span
        className={
          enough
            ? "text-right font-semibold tabular-nums"
            : "text-right text-muted-foreground tabular-nums"
        }
      >
        {percentOf(value, locale)}
      </span>
    </li>
  );
}

/** A panel's link to how its numbers are computed, named after the panel for screen readers
 * (the page has five of them). */
async function How({ metric, of }: { metric: string; of: string }) {
  const t = await getTranslations("teamStats");
  return (
    <Link href={`/formulas/${metric}`} className="text-link underline underline-offset-3">
      {t("how")}
      <span className="sr-only">{`, ${of}`}</span>
    </Link>
  );
}

function Sub({ children }: { children: ReactNode }) {
  return <h3 className="mt-3 mb-0.5 text-xs font-medium text-muted-foreground">{children}</h3>;
}

async function PlantPanel({
  title,
  metric,
  block,
}: {
  title: string;
  metric: string;
  block: TeamPlantBlock;
}) {
  const t = await getTranslations("teamStats");
  return (
    <Panel title={title} aside={<How metric={metric} of={title} />}>
      <p className="mb-2 text-xs text-muted-foreground">{t("plantHint")}</p>
      {block.rounds === 0 ? (
        <p className="text-sm text-muted-foreground">{t("noPlant")}</p>
      ) : (
        <>
          <ul>
            <RateRow name={<span className="font-medium">{t("allPlants")}</span>} count={block} />
          </ul>
          <Sub>{t("bySituation")}</Sub>
          <ul>
            {block.by_situation.map((s) => (
              <RateRow
                key={`${s.us}v${s.them}`}
                name={
                  <>
                    <span aria-hidden="true" className="tabular-nums">
                      {s.us}v{s.them}
                    </span>
                    <span className="sr-only">{t("situation", { us: s.us, them: s.them })}</span>
                  </>
                }
                count={s}
              />
            ))}
          </ul>
          <Sub>{t("bySite")}</Sub>
          <ul>
            {block.by_site.map((s) => (
              <RateRow key={s.site} name={t(`site.${s.site}`)} count={s} />
            ))}
          </ul>
        </>
      )}
    </Panel>
  );
}

/** Who trades whom: rows are the players who trade, columns those whose death they trade. A
 * cell is tinted by its count only when its column's player died at least `MIN_ROUNDS` times;
 * the count is always written. */
async function TradeNetwork({ stats }: { stats: TeamStats }) {
  const [t, locale] = await Promise.all([
    getTranslations("teamStats"),
    getLocale() as Promise<Locale>,
  ]);
  const { players, links } = stats.trades;
  const counts = new Map(links.map((l) => [`${l.trader}:${l.victim}`, l.count]));
  const most = Math.max(1, ...links.map((l) => l.count));
  const window = stats.trade_window_s ?? 5;
  return (
    <Panel title={t("trades")} aside={<How metric="team.trades" of={t("trades")} />}>
      <p className="mb-2 max-w-prose text-xs text-muted-foreground">
        {t("tradesHint", { window: number(window, locale) })}
      </p>
      {players.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("noTrades")}</p>
      ) : (
        // biome-ignore lint/a11y/noNoninteractiveTabindex: a region that may scroll sideways must be reachable by keyboard
        <section aria-label={t("trades")} tabIndex={0} className="overflow-x-auto">
          <table className="w-full min-w-[24rem] text-sm tabular-nums">
            <caption className="sr-only">{t("tradesCaption")}</caption>
            <thead>
              <tr className="text-xs text-muted-foreground">
                <th scope="col" className="px-2 py-1.5 text-left font-medium">
                  <span aria-hidden="true">{t("trader")}</span>
                  <span className="sr-only">{t("traderSr")}</span>
                </th>
                {players.map((p) => (
                  <th key={p.steam_id} scope="col" className="px-2 py-1.5 text-center font-medium">
                    <span title={p.name} className="block max-w-[6rem] truncate">
                      {p.name}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {players.map((row) => (
                <tr key={row.steam_id}>
                  <th scope="row" className="px-2 py-1 text-left font-semibold">
                    <span title={row.name} className="block max-w-[8rem] truncate">
                      {row.name}
                    </span>
                  </th>
                  {players.map((col) => {
                    const count = counts.get(`${row.steam_id}:${col.steam_id}`) ?? 0;
                    const tinted = col.deaths >= MIN_ROUNDS && count > 0;
                    return (
                      <td key={col.steam_id} className="p-0.5 text-center">
                        <span
                          title={t("cell", { trader: row.name, victim: col.name, count })}
                          className={
                            count === 0
                              ? "block rounded-sm py-1.5 text-muted-foreground"
                              : "block rounded-sm py-1.5"
                          }
                          style={
                            tinted
                              ? {
                                  backgroundColor: `color-mix(in srgb, var(--foreground) ${Math.round((count / most) * 26) + 4}%, transparent)`,
                                }
                              : undefined
                          }
                        >
                          {count}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-line-soft text-xs text-muted-foreground">
                <th scope="row" className="px-2 py-1.5 text-left font-medium">
                  {t("tradedDeaths")}
                </th>
                {players.map((p) => (
                  <td key={p.steam_id} className="px-2 py-1.5 text-center">
                    {t("won", { won: p.traded, rounds: p.deaths })}
                  </td>
                ))}
              </tr>
            </tfoot>
          </table>
        </section>
      )}
    </Panel>
  );
}

/** The team's tactical numbers: sites, post-plants and retakes, economy, trade network. */
export async function TeamStatsView({ stats }: { stats: TeamStats }) {
  const t = await getTranslations("teamStats");
  const maps = [...new Set(stats.sites.map((s) => s.map))];
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title={t("sites")} aside={<How metric="team.site_t" of={t("sites")} />}>
          <p className="mb-2 text-xs text-muted-foreground">{t("sitesHint")}</p>
          {maps.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("noRounds")}</p>
          ) : (
            maps.map((map) => (
              <div key={map}>
                <Sub>{mapName(map)}</Sub>
                <ul>
                  {stats.sites
                    .filter((s) => s.map === map)
                    .map((s) => (
                      <RateRow key={s.site} name={t(`site.${s.site}`)} count={s} />
                    ))}
                </ul>
              </div>
            ))
          )}
        </Panel>
        <Panel title={t("economy")} aside={<How metric="team.buy" of={t("economy")} />}>
          <p className="mb-2 text-xs text-muted-foreground">{t("economyHint")}</p>
          <ul>
            {stats.economy.map((e) => (
              <RateRow key={e.buy} name={t(`buys.${e.buy}`)} count={e} />
            ))}
          </ul>
        </Panel>
        <PlantPanel title={t("postPlant")} metric="team.post_plant" block={stats.post_plant} />
        <PlantPanel title={t("retakes")} metric="team.retake" block={stats.retakes} />
      </div>
      <TradeNetwork stats={stats} />
    </div>
  );
}
