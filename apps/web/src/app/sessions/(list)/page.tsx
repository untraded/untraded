// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { buttonVariants } from "@/components/ui/button";
import type { Locale } from "@/i18n/locale";
import { getSessions, type SessionSummary } from "@/lib/api";
import { cn } from "@/lib/cn";
import {
  byWeek,
  gap,
  gapTrend,
  hours,
  localDate,
  mapName,
  metric,
  monday,
  shortDay,
  type Trend,
  trendClass,
  weekdayDay,
} from "@/lib/format";

const PAGE = 20;
const ARROW: Record<Trend, string> = { better: "▲", worse: "▼", same: "=" };
const TREND_WORD: Record<Trend, "better" | "worse" | "stable"> = {
  better: "better",
  worse: "worse",
  same: "stable",
};
/** The two key figures of a row, with their short names in `matches`. */
const FIGURES = [
  ["rating.untraded", "urating"],
  ["base.adr", "adr"],
] as const;

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("sessions"))("title") };
}

/** The player's sessions by week: where each was played and what to work on after it. */
export default async function Sessions({
  searchParams,
}: {
  searchParams: Promise<{ offset?: string }>;
}) {
  const offset = Math.max(0, Number((await searchParams).offset ?? 0) || 0);
  const list = await getSessions(offset);
  if (!list) redirect("/");
  const t = await getTranslations("sessions");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const thisWeek = monday(localDate(new Date().toISOString(), timeZone));
  const lastWeek = new Date(Date.parse(`${thisWeek}T00:00:00Z`) - 7 * 86_400_000)
    .toISOString()
    .slice(0, 10);
  const weekLabel = (start: string) =>
    start === thisWeek
      ? t("thisWeek")
      : start === lastWeek
        ? t("lastWeek")
        : t("weekOf", { date: shortDay(`${start}T12:00:00Z`, locale, "UTC") });
  const pager = "h-8 gap-1.5 text-[0.8125rem]";
  return (
    <section className="flex flex-col gap-5">
      <header>
        <h1 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">{t("lead")}</p>
      </header>
      {list.items.length === 0 && <p className="text-muted-foreground">{t("empty")}</p>}
      {byWeek(list.items, timeZone).map((week) => {
        const total = (key: "wins" | "losses" | "ties") =>
          week.items.reduce((sum, s) => sum + s[key], 0);
        return (
          <section key={week.monday} aria-labelledby={`week-${week.monday}`}>
            <h2
              id={`week-${week.monday}`}
              className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3 text-sm font-semibold text-muted-foreground"
            >
              {weekLabel(week.monday)}{" "}
              <span className="font-normal">
                {t("weekSummary", {
                  sessions: week.items.length,
                  record: t("record", {
                    wins: total("wins"),
                    losses: total("losses"),
                    ties: total("ties"),
                  }),
                })}
              </span>
            </h2>
            <ul className="rounded-lg border border-border bg-card">
              {week.items.map((session) => (
                <SessionRow key={session.id} session={session} />
              ))}
            </ul>
          </section>
        );
      })}
      {(offset > 0 || list.items.length === PAGE) && (
        <nav className="flex items-center justify-between gap-3">
          {offset > 0 ? (
            <Link
              href={`/sessions?offset=${Math.max(0, offset - PAGE)}`}
              className={cn(buttonVariants({ variant: "outline" }), pager)}
            >
              <ChevronLeft aria-hidden="true" className="size-4" />
              {t("newer")}
            </Link>
          ) : (
            <span />
          )}
          <span className="text-[0.8125rem] text-muted-foreground">
            {t("pageOf", { from: offset + 1, to: offset + list.items.length })}
          </span>
          {list.items.length === PAGE ? (
            <Link
              href={`/sessions?offset=${offset + PAGE}`}
              className={cn(buttonVariants({ variant: "outline" }), pager)}
            >
              {t("older")}
              <ChevronRight aria-hidden="true" className="size-4" />
            </Link>
          ) : (
            <span />
          )}
        </nav>
      )}
    </section>
  );
}

async function SessionRow({ session }: { session: SessionSummary }) {
  const t = await getTranslations("sessions");
  const results = await getTranslations("result");
  const dashboard = await getTranslations("dashboard");
  const advice = await getTranslations("advice");
  const short = await getTranslations("matches");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const top = session.top_priority;
  const record =
    session.wins > session.losses ? "better" : session.losses > session.wins ? "worse" : "same";
  return (
    <li className="border-t border-line-soft first:border-t-0">
      <Link
        href={`/sessions/${session.id}`}
        className="grid grid-cols-[minmax(0,1fr)_1rem] gap-x-3 gap-y-1.5 rounded-lg px-3.5 py-3 hover:bg-muted md:grid-cols-[7.5rem_minmax(0,1fr)_15.5rem_1rem] md:items-center md:gap-x-4 md:px-4"
      >
        <span className="flex flex-wrap items-baseline gap-x-2 md:block">
          <span className="font-semibold md:block">
            {weekdayDay(session.started_at, locale, timeZone)}
          </span>
          <span className="text-xs text-muted-foreground">
            {hours(session.started_at, session.ended_at, locale, timeZone)}
          </span>
        </span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1 text-[0.8125rem]">
            <span className={cn("text-sm font-semibold", trendClass(record))}>
              {t("record", { wins: session.wins, losses: session.losses, ties: session.ties })}
            </span>
            <ul aria-label={t("mapsPlayed")} className="contents">
              {session.maps.map((played) => (
                <li key={played.match_id} className="inline-flex items-baseline gap-1.5">
                  {played.result && (
                    <>
                      <span
                        aria-hidden="true"
                        className={cn(
                          "rounded-sm px-1 text-[0.6875rem] font-bold",
                          played.result === "win" && "bg-win/15",
                          played.result === "loss" && "bg-loss/15",
                          played.result === "tie" && "bg-muted",
                        )}
                      >
                        {t(`resultShort.${played.result}`)}
                      </span>
                      <span className="sr-only">{results(played.result)}</span>
                    </>
                  )}
                  <span>{mapName(played.map)}</span>
                  {played.my_score !== null && played.their_score !== null && (
                    <span className="text-muted-foreground tabular-nums">
                      {played.my_score}–{played.their_score}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
          <p className="mt-1 text-[0.8125rem]">
            {top ? (
              <>
                <span className="sr-only">{t("topPriority")} </span>
                <span className="font-semibold">
                  <span aria-hidden="true">1. </span>
                  {advice(`rules.${top.rule_id}.label`)}
                </span>{" "}
                <span className="whitespace-nowrap text-muted-foreground">
                  {dashboard("lostOf", { lost: top.rounds_lost, touched: top.rounds_touched })}
                </span>
              </>
            ) : (
              <span className="text-muted-foreground">
                {session.enough ? t("nothingStandsOut") : t("noReferenceTitle")}
              </span>
            )}
          </p>
        </div>
        <dl className="grid grid-cols-2 gap-x-4 text-[0.8125rem] md:col-start-3">
          {FIGURES.map(([id, label]) => {
            const c = session.headlines.find((h) => h.metric_id === id);
            if (!c) return null;
            const moved = gapTrend(gap(c));
            return (
              <div key={id} className="flex items-baseline justify-between gap-1.5">
                <dt className="whitespace-nowrap text-muted-foreground">{short(label)}</dt>
                <dd className="whitespace-nowrap">
                  <span className="font-semibold">
                    {metric(c.session, c.unit, c.basis, locale)}
                  </span>
                  {session.enough && c.reference !== null ? (
                    <>
                      <span aria-hidden="true" className={cn("ml-1", trendClass(moved))}>
                        {ARROW[moved]}
                      </span>
                      <span className="sr-only"> ({t(TREND_WORD[moved])})</span>
                    </>
                  ) : (
                    // Keeps the values aligned with the rows that have an arrow.
                    <span aria-hidden="true" className="invisible ml-1">
                      {ARROW.same}
                    </span>
                  )}
                </dd>
              </div>
            );
          })}
        </dl>
        <ChevronRight
          aria-hidden="true"
          className="col-start-2 row-span-3 row-start-1 size-4 self-center text-muted-foreground md:col-start-4 md:row-span-1"
        />
      </Link>
    </li>
  );
}
