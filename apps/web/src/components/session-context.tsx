// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getLocale, getTranslations } from "next-intl/server";
import { MapChips } from "@/components/map-chips";
import { ContextBar } from "@/components/ui/context-bar";
import type { Locale } from "@/i18n/locale";
import type { SessionReport } from "@/lib/api";
import { cn } from "@/lib/cn";
import { delta, gap, gapTrend, mapName, metric, type Trend, trendClass } from "@/lib/format";

/** The three numbers the bar keeps in view, in this order. */
const KEY = [
  { id: "rating.untraded", label: "urating" },
  { id: "base.adr", label: "adr" },
  { id: "base.kast", label: "kast" },
] as const;
const ARROW = { better: "▲", worse: "▼", same: "=" } as const;
/** A match's page, which a chip of the bar links to. */
const matchHref = (id: string) => `/matches/${encodeURIComponent(id)}`;
/** The `id` of the report's list of the session's matches, which the "+n" of the matches links to. */
export const SESSION_MATCHES_ID = "session-matches";

/**
 * A session report's context bar: the session's record and its maps with their result and score,
 * on one line cut at the last map that fits with a "+n" for the rest (`MapChips`), and three key
 * numbers with their signed gap to the reference. The session's name is the report's own heading,
 * just below: the bar does not repeat it. On a phone it keeps the three numbers alone, on one
 * line, so that the priorities still start on the first screen; the matches are listed further
 * down the report.
 *
 * The chips link to their match for the mouse. The keyboard and assistive technologies get a list
 * of the same links, out of sight until focused: the focused one then shows over the record and
 * the first chips, so that no chip left on the hidden line takes the focus. From 1280 px the bar
 * holds on one line: with a very large font, the chips are clipped rather than scroll sideways.
 */
export async function SessionContext({ report }: { report: SessionReport }) {
  const [t, results, locale] = await Promise.all([
    getTranslations("sessions"),
    getTranslations("result"),
    getLocale() as Promise<Locale>,
  ]);
  const enough = report.reference.enough;
  const figures = KEY.flatMap(({ id, label }) => {
    const c = report.headlines.find((h) => h.metric_id === id);
    return c ? [{ c, label }] : [];
  });
  const record = { wins: report.wins, losses: report.losses, ties: report.ties };
  const trend: Trend =
    report.wins > report.losses ? "better" : report.losses > report.wins ? "worse" : "same";
  return (
    <ContextBar label={t("context.label")}>
      {report.maps.length > 0 && (
        <div className="relative flex min-w-min flex-1 items-baseline gap-x-2.5 text-[0.8125rem] max-sm:hidden xl:min-w-0 xl:overflow-x-clip xl:[overflow-clip-margin:0.5rem]">
          <span className={cn("shrink-0 text-sm font-semibold tabular-nums", trendClass(trend))}>
            {t("record", record)}
          </span>
          <ul
            aria-label={t("sessionMatches")}
            className="absolute top-1/2 left-0 z-10 w-max -translate-y-1/2"
          >
            {report.maps.map((played) => (
              <li key={played.match_id}>
                <Link
                  href={matchHref(played.match_id)}
                  className="sr-only focus:not-sr-only focus:inline-block focus:leading-7 focus:rounded-sm focus:bg-card focus:px-2 focus:text-xs focus:ring-1 focus:ring-border"
                >
                  {played.result && `${results(played.result)}, `}
                  <span translate="no">{mapName(played.map)}</span>
                  {played.my_score !== null &&
                    played.their_score !== null &&
                    `, ${played.my_score}–${played.their_score}`}
                </Link>
              </li>
            ))}
          </ul>
          <MapChips
            maps={report.maps}
            t={t}
            matchHref={matchHref}
            moreHref={`#${SESSION_MATCHES_ID}`}
          />
        </div>
      )}
      {figures.length > 0 && (
        <dl className="flex flex-wrap gap-x-4 gap-y-1 max-sm:w-full max-sm:justify-between sm:ml-auto sm:gap-x-6 xl:shrink-0 xl:flex-nowrap">
          {figures.map(({ c, label }) => {
            const moved = gapTrend(gap(c));
            return (
              <div key={c.metric_id} className="grid leading-tight">
                <dt translate="no" className="text-[0.6875rem] text-muted-foreground">
                  {t(`context.${label}`)}
                </dt>
                <dd className="flex items-baseline gap-1.5 whitespace-nowrap tabular-nums">
                  <span className="text-[0.9375rem] font-semibold">
                    {metric(c.session, c.unit, c.basis, locale)}
                  </span>
                  {enough && c.reference !== null && (
                    <span className={cn("text-xs", trendClass(moved))}>
                      <span aria-hidden="true">{ARROW[moved]}</span>{" "}
                      <span className="sr-only">{t("context.gap")} </span>
                      {delta(c.delta, c.unit, c.basis, locale)}
                    </span>
                  )}
                </dd>
              </div>
            );
          })}
        </dl>
      )}
    </ContextBar>
  );
}
