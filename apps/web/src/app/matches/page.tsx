// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { buttonVariants } from "@/components/ui/button";
import type { Locale } from "@/i18n/locale";
import { getMatches, type MatchSummary } from "@/lib/api";
import { cn } from "@/lib/cn";
import {
  byPeriod,
  mapName,
  number,
  type Period,
  percent,
  shortDay,
  time,
  weekdayDay,
} from "@/lib/format";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("matches"))("title") };
}
const PAGE = 30;

/** The columns of a row on wider screens: when, map, score, K–D, ADR, KAST, UD, rating, chevron. */
const COLUMNS =
  "md:grid-cols-[8.5rem_minmax(0,1fr)_5.5rem_5.5rem_3rem_3.5rem_3rem_4.5rem_1rem] md:items-center md:gap-x-4";

/**
 * The player's matches, newest first, grouped by period (today, yesterday, this week, last week,
 * the last 30 days, older) with each period's record. Each row opens the match.
 */
export default async function Matches({
  searchParams,
}: {
  searchParams: Promise<{ offset?: string }>;
}) {
  const offset = Math.max(0, Number((await searchParams).offset ?? 0) || 0);
  const list = await getMatches(offset);
  if (!list) redirect("/");
  const t = await getTranslations("matches");
  const s = await getTranslations("sessions");
  const timeZone = await getTimeZone();
  const now = new Date().toISOString();
  const pager = "h-8 gap-1.5 text-[0.8125rem]";
  return (
    <section className="flex flex-col gap-5">
      <h1 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
      {list.items.length === 0 && <p className="text-muted-foreground">{t("empty")}</p>}
      {byPeriod(list.items, now, timeZone).map((group, index) => {
        const count = (result: "win" | "loss" | "tie") =>
          group.items.filter((m) => m.my_result === result).length;
        const id = `period-${group.period}-${index}`;
        return (
          <section key={id} aria-labelledby={id}>
            <h2
              id={id}
              className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3 text-sm font-semibold text-muted-foreground"
            >
              {t(`periods.${group.period}`)}{" "}
              <span className="font-normal">
                {t("periodSummary", {
                  matches: group.items.length,
                  record: s("record", {
                    wins: count("win"),
                    losses: count("loss"),
                    ties: count("tie"),
                  }),
                })}
              </span>
            </h2>
            <div className="rounded-lg border border-border bg-card">
              {index === 0 && <ColumnHeads />}
              <ul>
                {group.items.map((match) => (
                  <MatchRow key={match.id} match={match} period={group.period} />
                ))}
              </ul>
            </div>
          </section>
        );
      })}
      {(offset > 0 || list.items.length === PAGE) && (
        <nav className="flex items-center justify-between gap-3">
          {offset > 0 ? (
            <Link
              href={`/matches?offset=${Math.max(0, offset - PAGE)}`}
              className={cn(buttonVariants({ variant: "outline" }), pager)}
            >
              <ChevronLeft aria-hidden="true" className="size-4" />
              {t("newer")}
            </Link>
          ) : (
            <span />
          )}
          <span className="text-[0.8125rem] text-muted-foreground">
            {s("pageOf", { from: offset + 1, to: offset + list.items.length })}
          </span>
          {list.items.length === PAGE ? (
            <Link
              href={`/matches?offset=${offset + PAGE}`}
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

/** The column names, above the first period on wider screens (hidden from screen readers: each
 * row names its numbers). */
async function ColumnHeads() {
  const t = await getTranslations("matches");
  return (
    <div
      aria-hidden="true"
      className={cn(
        "hidden border-b border-border px-4 py-2 text-xs font-medium text-muted-foreground md:grid",
        COLUMNS,
      )}
    >
      <span>{t("when")}</span>
      <span>{t("map")}</span>
      <span>{t("score")}</span>
      <span className="text-right">{t("kd")}</span>
      <span className="text-right">{t("adr")}</span>
      <span className="text-right">{t("kast")}</span>
      <span className="text-right" title={t("untraded")}>
        {t("untradedShort")}
      </span>
      <span className="text-right">{t("rating")}</span>
      <span />
    </div>
  );
}

async function MatchRow({ match, period }: { match: MatchSummary; period: Period }) {
  const t = await getTranslations("matches");
  const s = await getTranslations("sessions");
  const results = await getTranslations("result");
  const status = await getTranslations("status");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const at = match.played_at;
  const clock = time(at, locale, timeZone);
  const recent = !at || period === "today" || period === "yesterday";
  // Phones get the day without its weekday, so the row keeps to two lines.
  const when = recent ? clock : `${weekdayDay(at, locale, timeZone)}, ${clock}`;
  const whenShort = recent ? clock : `${shortDay(at, locale, timeZone)}, ${clock}`;
  const line = match.status === "ready" ? match.my_line : null;
  const mine = match.my_team === "B" ? match.score_b : match.score_a;
  const theirs = match.my_team === "B" ? match.score_a : match.score_b;
  const diff =
    line && line.kills !== null && line.deaths !== null ? line.kills - line.deaths : null;
  const signed = diff === null ? "" : diff > 0 ? `+${diff}` : `${diff}`;
  const label = "text-muted-foreground md:sr-only";
  return (
    <li className="border-t border-line-soft first:border-t-0">
      <Link
        href={`/matches/${match.id}`}
        className={cn(
          "grid grid-cols-[minmax(0,1fr)_auto_1rem] gap-x-3 gap-y-1 px-3.5 py-2.5 hover:bg-muted md:px-4",
          COLUMNS,
        )}
      >
        <span className="col-start-1 row-start-2 text-xs whitespace-nowrap text-muted-foreground tabular-nums md:row-start-1 md:text-sm">
          <span className="md:hidden">{whenShort}</span>
          <span className="hidden md:inline">{when}</span>
        </span>
        <span className="col-start-1 row-start-1 font-semibold md:col-start-2">
          {mapName(match.map)}
        </span>
        {match.status === "ready" && match.my_result && mine !== null && theirs !== null ? (
          <span className="col-start-2 row-start-1 flex items-center justify-end gap-2 font-semibold tabular-nums md:col-start-3 md:justify-start">
            <span
              aria-hidden="true"
              className={cn(
                "grid size-5 place-items-center rounded-[3px] text-[0.6875rem] font-bold",
                match.my_result === "win" && "bg-win/15",
                match.my_result === "loss" && "bg-loss/15",
                match.my_result === "tie" && "bg-muted",
              )}
            >
              {s(`resultShort.${match.my_result}`)}
            </span>
            <span className="sr-only">{results(match.my_result)}</span>
            {mine} – {theirs}
          </span>
        ) : (
          <span className="col-start-2 row-start-1 text-right text-[0.8125rem] text-muted-foreground md:col-span-6 md:col-start-3 md:text-left">
            <span className="md:hidden">{status(match.status)}</span>
            <span className="hidden md:inline">{t(`waiting.${match.status}`)}</span>
          </span>
        )}
        {line && (
          <>
            <span className="col-start-2 row-start-2 text-right text-xs whitespace-nowrap text-muted-foreground tabular-nums md:hidden">
              <span className="sr-only">{t("kd")} </span>
              {number(line.kills, locale)}–{number(line.deaths, locale)} ·{" "}
              <span className="sr-only">{t("rating")} </span>
              {number(line.hltv1, locale, 2)}
            </span>
            <span className="hidden text-right whitespace-nowrap tabular-nums md:block">
              <span className={label}>{t("kd")} </span>
              {number(line.kills, locale)}–{number(line.deaths, locale)}{" "}
              <span className="text-xs text-muted-foreground">{signed}</span>
            </span>
            <span className="hidden text-right tabular-nums md:block">
              <span className={label}>{t("adr")} </span>
              {number(line.adr, locale)}
            </span>
            <span className="hidden text-right tabular-nums md:block">
              <span className={label}>{t("kast")} </span>
              {percent(line.kast, locale)}
            </span>
            <span className="hidden text-right tabular-nums md:block">
              <span className={label}>{t("untraded")} </span>
              {number(line.untraded_deaths, locale)}
            </span>
            <span className="hidden text-right font-semibold tabular-nums md:block">
              <span className={label}>{t("rating")} </span>
              {number(line.hltv1, locale, 2)}
            </span>
          </>
        )}
        <ChevronRight
          aria-hidden="true"
          className="col-start-3 row-span-2 row-start-1 size-4 self-center text-muted-foreground md:col-start-9 md:row-span-1"
        />
      </Link>
    </li>
  );
}
