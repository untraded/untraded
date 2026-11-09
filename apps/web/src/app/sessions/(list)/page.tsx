// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { SessionRow, SessionRowsHeader } from "@/components/session-row";
import { buttonVariants } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type { Locale } from "@/i18n/locale";
import { getSessions } from "@/lib/api";
import { cn } from "@/lib/cn";
import { byWeek, localDate, monday, shortDay } from "@/lib/format";

const PAGE = 20;

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
    <section className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">{t("lead")}</p>
      </header>
      {list.items.length === 0 && (
        <p className="rounded-lg border border-border bg-card px-3.5 py-3 text-sm text-muted-foreground">
          {t("empty")}
        </p>
      )}
      {byWeek(list.items, timeZone).map((week) => {
        const total = (key: "wins" | "losses" | "ties") =>
          week.items.reduce((sum, s) => sum + s[key], 0);
        const summary = t("weekSummary", {
          sessions: week.items.length,
          record: t("record", {
            wins: total("wins"),
            losses: total("losses"),
            ties: total("ties"),
          }),
        });
        // The summary is read with the heading, as the week's heading said it before.
        return (
          <Panel
            key={week.monday}
            title={
              <>
                {weekLabel(week.monday)}
                <span className="sr-only">, {summary}</span>
              </>
            }
            aside={<span aria-hidden="true">{summary}</span>}
            flush
          >
            <SessionRowsHeader />
            <ul>
              {week.items.map((session) => (
                <SessionRow key={session.id} session={session} />
              ))}
            </ul>
          </Panel>
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
