// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronRight, Compass, Dumbbell, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { FollowUpList } from "@/components/follow-up";
import { describeReference } from "@/components/reference";
import { buttonVariants } from "@/components/ui/button";
import type { Locale, Tone } from "@/i18n/locale";
import {
  type Advice,
  getMatches,
  getSession,
  getSessions,
  type MatchStatus,
  type SessionSummary,
} from "@/lib/api";
import { cn } from "@/lib/cn";
import {
  dateRange,
  gap,
  gapTrend,
  mapName,
  metric,
  shortDay,
  type Trend,
  time,
} from "@/lib/format";

const IN_PROGRESS: MatchStatus[] = ["pending", "downloading", "parsing"];
const ARROW: Record<Trend, string> = { better: "▲", worse: "▼", same: "=" };

/**
 * The signed-in home page: the latest session and its priorities, what to work on before playing
 * again, the progress of the previous priorities, and the matches still being analysed. On a
 * phone it fits about one screen: shorter priorities, no instructions, no recent sessions.
 */
export async function Dashboard({ tone }: { tone: Tone }) {
  const t = await getTranslations("dashboard");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const [sessions, matches] = await Promise.all([getSessions(0), getMatches(0)]);
  const pending = (matches?.items ?? []).filter((m) => IN_PROGRESS.includes(m.status));
  const latest = sessions?.items[0];
  const report = latest ? await getSession(latest.id) : null;
  const first = pending[0];

  return (
    <div className="flex flex-col gap-3 md:gap-6">
      <h1 className="sr-only text-2xl font-semibold md:not-sr-only md:text-[1.75rem]">
        {t("title")}
      </h1>
      {first && (
        <p className="flex items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-2 text-[0.8125rem] text-muted-foreground md:hidden">
          <LoaderCircle
            aria-hidden="true"
            className="size-4 animate-spin motion-reduce:animate-none"
          />
          {t("pendingShort", {
            map: mapName(first.map),
            time: time(first.played_at, locale, timeZone),
          })}
        </p>
      )}
      {!report ? (
        <Card>
          <p className="text-muted-foreground">{(await getTranslations("sessions"))("empty")}</p>
        </Card>
      ) : (
        <div className="grid items-start gap-3 md:gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="flex flex-col gap-3 md:gap-4">
            <Latest report={report} tone={tone} locale={locale} />
            {sessions && sessions.items.length > 1 && (
              <Recent items={sessions.items.slice(0, 5)} locale={locale} />
            )}
          </div>
          <div className="flex flex-col gap-3 md:gap-4">
            {report.advice[0] && <WorkOn item={report.advice[0]} />}
            {report.follow_up.length > 0 && (
              <Card>
                <h2 className="text-[0.8125rem] text-muted-foreground md:text-base md:font-semibold md:text-foreground">
                  {t("progress")}
                </h2>
                <p className="mb-2 hidden text-[0.8125rem] text-muted-foreground md:block">
                  {t("progressLead")}
                </p>
                <div className="mt-1.5 md:mt-0">
                  <FollowUpList items={report.follow_up} locale={locale} compact />
                </div>
              </Card>
            )}
            {first && (
              <Card className="hidden md:block">
                <div className="flex gap-3">
                  <LoaderCircle
                    aria-hidden="true"
                    className="mt-0.5 size-4 shrink-0 animate-spin text-muted-foreground motion-reduce:animate-none"
                  />
                  <div>
                    <h2 className="text-[0.9375rem] font-semibold">
                      {t("pendingTitle", { count: pending.length })}
                    </h2>
                    <p className="text-[0.8125rem] text-muted-foreground">
                      {t("pendingBody", {
                        map: mapName(first.map),
                        time: time(first.played_at, locale, timeZone),
                      })}
                    </p>
                  </div>
                </div>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

async function Latest({
  report,
  tone,
  locale,
}: {
  report: NonNullable<Awaited<ReturnType<typeof getSession>>>;
  tone: Tone;
  locale: Locale;
}) {
  const t = await getTranslations("dashboard");
  const sessions = await getTranslations("sessions");
  const advice = await getTranslations("advice");
  const named = await describeReference(report.reference, locale);
  const timeZone = await getTimeZone();
  return (
    <Card>
      <p className="text-[0.8125rem] text-muted-foreground">{t("latest")}</p>
      <h2 className="text-lg font-semibold md:text-[1.3125rem]">
        {sessions("titleOf", { date: shortDay(report.started_at, locale, timeZone) })}
      </h2>
      <p className="mt-0.5 flex flex-wrap gap-x-3.5 gap-y-0.5 text-sm text-muted-foreground">
        <span className="hidden md:inline">
          {dateRange(report.started_at, report.ended_at, locale, timeZone)}
        </span>
        <span>{sessions("count", { matches: report.matches, rounds: report.rounds })}</span>
        <span className="font-semibold text-foreground">
          {sessions("record", { wins: report.wins, losses: report.losses, ties: report.ties })}
        </span>
      </p>
      {report.advice.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">
          {report.reference.enough ? advice("none") : advice("noReference")}
        </p>
      ) : (
        <ol className="mt-2.5 md:mt-4">
          {report.advice.map((item) => (
            <li
              key={item.id}
              className="grid grid-cols-[1.125rem_minmax(0,1fr)_auto] items-baseline gap-x-2.5 border-t border-line-soft py-1.5 md:grid-cols-[1.375rem_minmax(0,1fr)] md:py-2.5"
            >
              <span className="font-semibold text-muted-foreground">{item.priority}</span>
              <span className="text-[0.9375rem] font-semibold">
                <span className="md:hidden">{advice(`rules.${item.rule_id}.label`)}</span>
                <span className="hidden md:inline">{finding(item, tone, advice, locale)}</span>
              </span>
              <span className="text-[0.8125rem] whitespace-nowrap text-muted-foreground md:col-start-2">
                <span className="md:hidden">
                  {t("lostOf", { lost: item.args.rounds_lost, touched: item.args.rounds_touched })}
                </span>
                <span className="hidden md:inline">
                  {advice("costLong", {
                    touched: item.args.rounds_touched,
                    lost: item.args.rounds_lost,
                  })}
                </span>
              </span>
            </li>
          ))}
        </ol>
      )}
      {named.short && (
        <p className="mt-2 hidden text-[0.8125rem] text-muted-foreground md:block">
          {sessions("referenceLabel", { reference: named.short })}
        </p>
      )}
      <Link
        href={`/sessions/${report.id}`}
        className={cn(buttonVariants(), "mt-3 w-full md:mt-4 md:w-auto")}
      >
        {t("openReport")}
      </Link>
    </Card>
  );
}

/** The finding of a priority, in the chosen tone (the same text as in the report). */
function finding(
  item: Advice,
  tone: Tone,
  t: Awaited<ReturnType<typeof getTranslations<"advice">>>,
  locale: Locale,
): string {
  const { args } = item;
  const basis = args.basis === "pattern" ? "value" : args.basis;
  return t(`rules.${item.rule_id}.${tone}`, {
    events: args.events,
    session: metric(args.session, args.unit, basis, locale),
    reference: metric(args.reference, args.unit, basis, locale),
    zone: args.zone ?? "",
    map: mapName(args.map ?? null),
    side: args.side ?? "",
    history: args.history_events ?? 0,
  });
}

async function WorkOn({ item }: { item: Advice }) {
  const t = await getTranslations("dashboard");
  const advice = await getTranslations("advice");
  const actions = await getTranslations("actions");
  const known = item.args.actions.filter((id) => actions.has(`${id}.title`)).slice(0, 2);
  if (known.length === 0) return null;
  return (
    <Card>
      <p className="text-[0.8125rem] text-muted-foreground">{t("work")}</p>
      <h2 className="mt-0.5 hidden text-[0.9375rem] font-semibold md:block">
        {advice(`rules.${item.rule_id}.label`)}
      </h2>
      <p className="hidden text-sm text-muted-foreground md:block">{t("workLead")}</p>
      <ul className="mt-1 md:mt-2">
        {known.map((id) => {
          const kind = id.split(".")[0] ?? "";
          const Icon = kind === "drill" ? Dumbbell : Compass;
          return (
            <li
              key={id}
              className="grid grid-cols-[1rem_minmax(0,1fr)] gap-x-2.5 py-1.5 md:border-t md:border-line-soft md:py-2.5"
            >
              <Icon aria-hidden="true" className="mt-1 size-4 text-muted-foreground" />
              <div className="text-sm">
                <span className="font-semibold">{actions(`${id}.title`)}</span>{" "}
                <span className="text-xs text-muted-foreground">{actions(`kinds.${kind}`)}</span>
                <p className="mt-0.5 hidden text-muted-foreground md:block">
                  {actions(`${id}.how`)}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

async function Recent({ items, locale }: { items: SessionSummary[]; locale: Locale }) {
  const t = await getTranslations("dashboard");
  const timeZone = await getTimeZone();
  const sessions = await getTranslations("sessions");
  return (
    <Card className="hidden md:block">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="font-semibold">{t("recent")}</h2>
        <Link href="/sessions" className={buttonVariants({ variant: "link" })}>
          {t("allSessions")}
        </Link>
      </div>
      <ul className="mt-2">
        {items.map((session) => (
          <li key={session.id} className="border-t border-line-soft first:border-t-0">
            <Link
              href={`/sessions/${session.id}`}
              className="-mx-2 grid grid-cols-[7.5rem_minmax(0,1fr)_auto_1rem] items-center gap-3.5 rounded-md px-2 py-2.5 text-sm hover:bg-muted"
            >
              <span>
                <span className="block font-semibold">
                  {shortDay(session.started_at, locale, timeZone)}
                </span>
                <span className="text-xs text-muted-foreground">
                  {sessions("count", { matches: session.matches, rounds: session.rounds })}
                </span>
              </span>
              <span
                className={cn(
                  "font-semibold",
                  session.wins > session.losses
                    ? "text-win"
                    : session.losses > session.wins
                      ? "text-loss"
                      : "text-muted-foreground",
                )}
              >
                {sessions("record", {
                  wins: session.wins,
                  losses: session.losses,
                  ties: session.ties,
                })}
              </span>
              <span className="flex gap-4 text-[0.8125rem] text-muted-foreground">
                {session.headlines
                  .filter((c) => c.metric_id === "base.adr" || c.metric_id === "base.kast")
                  .map((c) => {
                    const moved = gapTrend(gap(c));
                    return (
                      <span key={c.metric_id} className="whitespace-nowrap">
                        {c.name}{" "}
                        <span className="font-semibold text-foreground">
                          {metric(c.session, c.unit, c.basis, locale)}
                        </span>
                        {session.enough && (
                          <span
                            aria-hidden="true"
                            className={cn(
                              "ml-1",
                              moved === "better"
                                ? "text-win"
                                : moved === "worse"
                                  ? "text-loss"
                                  : "text-muted-foreground",
                            )}
                          >
                            {ARROW[moved]}
                          </span>
                        )}
                      </span>
                    );
                  })}
              </span>
              <ChevronRight aria-hidden="true" className="size-4 text-muted-foreground" />
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <section
      className={cn("rounded-lg border border-border bg-card p-3.5 md:px-5 md:py-4", className)}
    >
      {children}
    </section>
  );
}
