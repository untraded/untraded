// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getLocale, getTranslations } from "next-intl/server";
import { ContextBar } from "@/components/ui/context-bar";
import type { Locale } from "@/i18n/locale";
import type { SessionReport } from "@/lib/api";
import { cn } from "@/lib/cn";
import { delta, gap, gapTrend, mapName, metric, score, trendClass } from "@/lib/format";

/** The three numbers the bar keeps in view, in this order. */
const KEY = [
  { id: "rating.untraded", label: "urating" },
  { id: "base.adr", label: "adr" },
  { id: "base.kast", label: "kast" },
] as const;
const ARROW = { better: "▲", worse: "▼", same: "=" } as const;
/**
 * The most matches the bar lists one by one: three still hold on one line beside the key numbers
 * at 1280 px. A longer session is summed up ("4 matches · 0 W – 4 L"), with a link to the report's
 * list of its matches, so that the bar never scrolls sideways.
 */
export const MAX_LISTED_MATCHES = 3;
/** The `id` of the report's list of the session's matches, which the summary links to. */
export const SESSION_MATCHES_ID = "session-matches";

/**
 * A session report's context bar: the session's matches with their score and result (a dot and the
 * word, never the colour alone), or their summary past three, and three key numbers with their
 * signed gap to the reference. The session's name is the report's own heading, just below: the bar
 * does not repeat it. On a phone it keeps the three numbers alone, on one line, so that the
 * priorities still start on the first screen; the matches are listed further down the report.
 */
export async function SessionContext({ report }: { report: SessionReport }) {
  const [t, results, status, locale] = await Promise.all([
    getTranslations("sessions"),
    getTranslations("result"),
    getTranslations("status"),
    getLocale() as Promise<Locale>,
  ]);
  const enough = report.reference.enough;
  const figures = KEY.flatMap(({ id, label }) => {
    const c = report.headlines.find((h) => h.metric_id === id);
    return c ? [{ c, label }] : [];
  });
  const matches = report.match_list;
  const record = { wins: report.wins, losses: report.losses, ties: report.ties };
  return (
    <ContextBar label={t("context.label")}>
      {matches.length > MAX_LISTED_MATCHES ? (
        <a
          href={`#${SESSION_MATCHES_ID}`}
          className="inline-flex h-7 items-center gap-2 rounded-sm bg-muted px-2 text-xs whitespace-nowrap hover:bg-band max-sm:hidden xl:shrink-0"
        >
          <span className="font-semibold">{t("context.matches", { count: matches.length })}</span>{" "}
          <span className="text-muted-foreground">{t("record", record)}</span>
          <span className="sr-only">{t("context.toMatches")}</span>
        </a>
      ) : (
        matches.length > 0 && (
          <ul
            aria-label={t("sessionMatches")}
            className="flex flex-wrap gap-1.5 max-sm:hidden xl:min-w-0"
          >
            {matches.map((match) => {
              const result = match.status === "ready" ? match.my_result : null;
              return (
                <li key={match.id} className="shrink-0">
                  <Link
                    href={`/matches/${encodeURIComponent(match.id)}`}
                    className="inline-flex h-7 items-center gap-2 rounded-sm bg-muted px-2 text-xs whitespace-nowrap hover:bg-band"
                  >
                    <span className="font-semibold">
                      {mapName(match.map)} {score(match.score_a, match.score_b, match.my_team)}
                    </span>
                    <span className="inline-flex items-center gap-1 text-muted-foreground">
                      {result && (
                        <span
                          aria-hidden="true"
                          className={cn(
                            "size-2 rounded-full",
                            result === "win" && "bg-win",
                            result === "loss" && "bg-loss",
                            result === "tie" && "bg-muted-foreground",
                          )}
                        />
                      )}
                      {result ? results(result) : status(match.status)}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )
      )}
      {figures.length > 0 && (
        <dl className="flex flex-wrap gap-x-4 gap-y-1 max-sm:w-full max-sm:justify-between sm:gap-x-6 lg:ml-auto xl:shrink-0 xl:flex-nowrap">
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
