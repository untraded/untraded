// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { FollowUpList } from "@/components/follow-up";
import { type ChartPoint, ProgressChart } from "@/components/progress/progress-chart";
import type { Locale } from "@/i18n/locale";
import { findSession, sessionsBack } from "@/lib/api";
import { cn } from "@/lib/cn";
import { gapTrend, metric, percent, shortDay, trendClass } from "@/lib/format";
import {
  change,
  geometry,
  inPeriod,
  KEY_FIGURES,
  NARROW,
  PERIODS,
  periodDays,
  pickPeriod,
  type Series,
  series,
  WIDE,
} from "@/lib/progress";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("progress"))("title") };
}

/** The short names the lists use for the key figures (`matches`). */
const NAMES: Record<(typeof KEY_FIGURES)[number], string> = {
  "rating.hltv1": "rating",
  "base.adr": "adr",
  "base.kast": "kast",
  "trade.untraded_deaths": "untraded",
};
const ARROW = { better: "▲", worse: "▼", same: "=" } as const;

/**
 * The player's key figures session after session against their reference, over a period (the
 * last 10 sessions, 30 days, 3 months or all), then the previous priorities and their indicator.
 */
export default async function Progress({
  searchParams,
}: {
  searchParams: Promise<{ period?: string }>;
}) {
  const period = pickPeriod((await searchParams).period);
  const now = Date.now();
  const days = periodDays(period);
  const all = await sessionsBack(
    days === null ? null : now - days * 86_400_000,
    period === "last10" ? 10 : null,
  );
  if (!all) redirect("/");
  const t = await getTranslations("progress");
  const m = await getTranslations("matches");
  const s = await getTranslations("sessions");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const sessions = inPeriod(all, period, now);
  // The previous priorities come from the newest report, an extra the page stands without.
  const latest = all[0] ? await findSession(all[0].id) : null;
  const first = sessions[0];
  const last = sessions.at(-1);

  return (
    <section className="flex flex-col gap-5">
      <header className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
        <p className="max-w-prose text-sm text-muted-foreground">{t("lead")}</p>
      </header>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <nav
          aria-label={t("period")}
          className="inline-flex overflow-hidden rounded-md border border-border"
        >
          {PERIODS.map((p) => (
            <Link
              key={p}
              href={p === "days30" ? "/progress" : `/progress?period=${p}`}
              aria-current={p === period ? "page" : undefined}
              className={cn(
                "flex h-8 items-center border-l border-border bg-card px-3 text-[0.8125rem] first:border-l-0 hover:bg-muted",
                p === period && "bg-highlight-soft font-semibold hover:bg-highlight-soft",
              )}
            >
              {t(`periods.${p}`)}
            </Link>
          ))}
        </nav>
        {first && last && (
          <span className="text-[0.8125rem] text-muted-foreground">
            {t("range", {
              count: sessions.length,
              from: shortDay(first.started_at, locale, timeZone),
              to: shortDay(last.started_at, locale, timeZone),
            })}
          </span>
        )}
        <span aria-hidden="true" className="flex gap-3.5 text-xs text-muted-foreground sm:ml-auto">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-4 border-t-2 border-foreground" />
            {t("you")}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-4 border-t-2 border-dashed border-muted-foreground" />
            {t("reference")}
          </span>
        </span>
      </div>

      {sessions.length === 0 ? (
        <p className="rounded-lg border border-border bg-card p-4 text-muted-foreground">
          {all.length === 0 ? t("noSession") : t("noSessionInPeriod")}
        </p>
      ) : (
        <div className="grid gap-3.5 md:grid-cols-2">
          {KEY_FIGURES.map((id) => {
            const line = series(sessions, id);
            return line ? (
              <FigureCard
                key={id}
                line={line}
                name={m(NAMES[id])}
                perRound={line.basis === "per_round" ? s("perRound") : null}
                locale={locale}
                timeZone={timeZone}
              />
            ) : null;
          })}
        </div>
      )}

      <section aria-labelledby="progress-priorities" className="flex flex-col gap-2">
        <h2 id="progress-priorities" className="text-sm font-semibold text-muted-foreground">
          {t("priorities")}
        </h2>
        <div className="rounded-lg border border-border bg-card p-4">
          {latest && latest.follow_up.length > 0 ? (
            <FollowUpList items={latest.follow_up} locale={locale} />
          ) : (
            <p className="text-sm text-muted-foreground">{t("noPriority")}</p>
          )}
        </div>
      </section>
    </section>
  );
}

async function FigureCard({
  line,
  name,
  perRound,
  locale,
  timeZone,
}: {
  line: Series;
  name: string;
  perRound: string | null;
  locale: Locale;
  timeZone: string;
}) {
  const t = await getTranslations("progress");
  const format = (value: number | null) => metric(value, line.unit, line.basis, locale);
  const moved = change(line.points, line.better);
  const trend = gapTrend(moved);
  const newest = line.points.at(-1);
  const measured = line.points.filter((p) => p.value !== null).length;
  const points: ChartPoint[] = line.points.map((p) => {
    const date = shortDay(p.startedAt, locale, timeZone);
    const reference = p.reference === null ? null : t("ref", { value: format(p.reference) });
    const gap =
      p.value === null || p.reference === null || p.reference === 0 || line.better === "neutral"
        ? null
        : ((p.value - p.reference) / Math.abs(p.reference)) *
          100 *
          (line.better === "lower" ? -1 : 1);
    return {
      date,
      value: format(p.value),
      reference,
      trend: gap === null ? null : gapTrend(gap),
    };
  });
  const wide = measured > 1 ? geometry(line.points, WIDE) : null;
  const narrow = measured > 1 ? geometry(line.points, NARROW) : null;
  const label = t("chart", {
    name,
    count: line.points.length,
    from: points[0]?.value ?? "",
    to: points.at(-1)?.value ?? "",
  });
  return (
    <article className="@container rounded-lg border border-border bg-card px-4 pt-3.5 pb-2.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <h2 className="font-semibold">
          {name}
          {perRound && (
            <span className="ml-1.5 text-xs font-normal text-muted-foreground">{perRound}</span>
          )}
        </h2>
        {moved !== null && (
          <span className={cn("text-[0.8125rem] whitespace-nowrap", trendClass(trend))}>
            <span aria-hidden="true">{ARROW[trend]}</span>{" "}
            {trend === "same"
              ? t("stable")
              : t(trend === "better" ? "betterBy" : "worseBy", {
                  gap: percent(Math.abs(moved), locale),
                })}
          </span>
        )}
      </div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span className="text-2xl font-semibold tabular-nums">{format(newest?.value ?? null)}</span>
        <span className="text-[0.8125rem] text-muted-foreground tabular-nums">
          {t("latest")}
          {newest?.reference !== null &&
            newest?.reference !== undefined &&
            ` · ${t("ref", { value: format(newest.reference) })}`}
        </span>
      </div>
      {wide && narrow ? (
        // Drawn at the card's width (a container query), so the axes keep a readable size; the
        // table says the same to screen readers.
        <div>
          {[narrow, wide].map((g) => (
            <div key={g.width} className={g === wide ? "hidden @md:block" : "@md:hidden"}>
              <ProgressChart
                geometry={g}
                points={points}
                ticks={g.ticks.map((tick) => format(tick.value))}
              />
            </div>
          ))}
          {/* `sr-only` on the table itself does not hide it: a table grows to its content, and the
              page then scrolls sideways on phones. */}
          <div className="sr-only">
            <table>
              <caption>{label}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("date")}</th>
                  <th scope="col">{t("you")}</th>
                  <th scope="col">{t("reference")}</th>
                </tr>
              </thead>
              <tbody>
                {points.map((p, i) => (
                  <tr key={line.points[i]?.sessionId}>
                    <th scope="row">{p.date}</th>
                    <td>{p.value}</td>
                    <td>{p.reference ?? "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <p className="py-6 text-[0.8125rem] text-muted-foreground">{t("tooFew")}</p>
      )}
    </article>
  );
}
