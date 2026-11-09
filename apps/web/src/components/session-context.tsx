// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { ContextBar } from "@/components/ui/context-bar";
import type { Locale } from "@/i18n/locale";
import type { SessionReport } from "@/lib/api";
import { cn } from "@/lib/cn";
import { delta, gap, gapTrend, mapName, metric, score, shortDay, trendClass } from "@/lib/format";

/** The three numbers the bar keeps in view, in this order. */
const KEY = [
  { id: "rating.untraded", label: "urating" },
  { id: "base.adr", label: "adr" },
  { id: "base.kast", label: "kast" },
] as const;
const ARROW = { better: "▲", worse: "▼", same: "=" } as const;

/**
 * A session report's context bar: which session, its matches with their score and result (a dot
 * and the word, never the colour alone), and three key numbers with their signed gap to the
 * reference.
 */
export async function SessionContext({ report }: { report: SessionReport }) {
  const t = await getTranslations("sessions");
  const results = await getTranslations("result");
  const status = await getTranslations("status");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const enough = report.reference.enough;
  const figures = KEY.flatMap(({ id, label }) => {
    const c = report.headlines.find((h) => h.metric_id === id);
    return c ? [{ c, label }] : [];
  });
  return (
    <ContextBar label={t("context.label")}>
      <p className="font-semibold xl:shrink-0">
        {t("titleOf", { date: shortDay(report.started_at, locale, timeZone) })}
      </p>
      {report.match_list.length > 0 && (
        <ul
          aria-label={t("sessionMatches")}
          className="flex flex-wrap gap-1.5 xl:-m-1 xl:min-w-0 xl:flex-nowrap xl:overflow-x-auto xl:p-1 xl:[scrollbar-width:thin]"
        >
          {report.match_list.map((match) => {
            const result = match.status === "ready" ? match.my_result : null;
            return (
              <li key={match.id} className="shrink-0">
                <Link
                  href={`/matches/${encodeURIComponent(match.id)}`}
                  className="inline-flex h-7 items-center gap-2 rounded-sm bg-muted px-2 text-xs hover:bg-band"
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
      )}
      {figures.length > 0 && (
        <dl className="flex flex-wrap gap-x-6 gap-y-1 lg:ml-auto xl:shrink-0 xl:flex-nowrap">
          {figures.map(({ c, label }) => {
            const moved = gapTrend(gap(c));
            return (
              <div key={c.metric_id} className="grid leading-tight">
                <dt translate="no" className="text-[0.6875rem] text-muted-foreground">
                  {t(`context.${label}`)}
                </dt>
                <dd className="flex items-baseline gap-1.5">
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
