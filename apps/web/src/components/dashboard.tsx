// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { Compass, Dumbbell, LoaderCircle, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { Suspense } from "react";
import { FollowUpList, FollowUpSkeleton } from "@/components/follow-up";
import { describeReference } from "@/components/reference";
import {
  Figures,
  SessionRow,
  SessionRowSkeleton,
  SessionRowsHeader,
} from "@/components/session-row";
import { Loading, Skeleton, SkeletonLine, slots } from "@/components/skeleton";
import { buttonVariants } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type { Locale, Tone } from "@/i18n/locale";
import {
  type Advice,
  findMatches,
  findSession,
  findSessions,
  type MatchStatus,
  type Me,
  type SessionReport,
  type SessionSummary,
} from "@/lib/api";
import { cn } from "@/lib/cn";
import { dateRange, mapName, metric, shortDay, time } from "@/lib/format";

const IN_PROGRESS: MatchStatus[] = ["pending", "downloading", "parsing"];
/** The sessions listed under the latest one. */
const RECENT = 5;
/** The body of the head panels (the latest session, the wait for a first one): roomier. */
const HEAD_BODY = "px-3.5 py-3 md:px-5 md:py-4";

/**
 * The signed-in home page, in one order of importance: the latest session with its priorities
 * and the one action, opening its report; then what to work on before playing again and the
 * progress of the previous priorities, side by side and quieter; then the sessions before it and
 * the matches still being analysed. On a phone it fits about one screen: shorter priorities, no
 * instructions, no recent sessions, the analysis in one line at the top.
 *
 * No context bar: the page is not about one session or match but leads to them, and a bar would
 * repeat the latest session's panel right under it.
 *
 * The title is sent at once; the session's report and the matches being analysed each stream in
 * when the API gives them, so neither waits on the other.
 */
export async function Dashboard({ me, tone }: { me: Me; tone: Tone }) {
  const t = await getTranslations("dashboard");
  return (
    <div className="flex flex-col gap-3 md:gap-4">
      <h1 className="sr-only text-2xl font-semibold md:not-sr-only md:text-[1.75rem]">
        {t("title")}
      </h1>
      {/* Nothing while loading: there is rarely a match being analysed, and a placeholder would
          then leave an empty line above the report. */}
      <Suspense fallback={null}>
        <PendingShort />
      </Suspense>
      {me.source?.last_error && (
        <p
          role="status"
          className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-destructive/40 bg-card px-3 py-2.5 text-sm"
        >
          <TriangleAlert aria-hidden="true" className="size-4 shrink-0 text-destructive" />
          {t("codesBroken")}
          <Link href="/settings" className={buttonVariants({ variant: "link" })}>
            {t("codesBrokenLink")}
          </Link>
        </p>
      )}
      <Suspense
        fallback={
          <Loading announce={false} className="flex flex-col gap-3 md:gap-4">
            <SessionsSkeleton />
          </Loading>
        }
      >
        <Sessions tone={tone} />
      </Suspense>
    </div>
  );
}

/** The matches still being analysed, newest first (fetched once per request). Streamed after the
 * page started, so an API failure shows nothing rather than an error screen. */
async function pendingMatches() {
  return ((await findMatches(0))?.items ?? []).filter((m) => IN_PROGRESS.includes(m.status));
}

/** The match being analysed, in one line on a phone. */
async function PendingShort() {
  const [pending, t, locale, timeZone] = await Promise.all([
    pendingMatches(),
    getTranslations("dashboard"),
    getLocale() as Promise<Locale>,
    getTimeZone(),
  ]);
  const first = pending[0];
  if (!first) return null;
  return (
    <p className="flex items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-2 text-[0.8125rem] text-muted-foreground md:hidden">
      <LoaderCircle aria-hidden="true" className="size-4 animate-spin motion-reduce:animate-none" />
      {t("pendingShort", {
        map: mapName(first.map),
        time: time(first.played_at, locale, timeZone),
      })}
    </p>
  );
}

/** The matches being analysed, in a panel at the end of the page on a computer. */
async function PendingPanel() {
  const [pending, t, locale, timeZone] = await Promise.all([
    pendingMatches(),
    getTranslations("dashboard"),
    getLocale() as Promise<Locale>,
    getTimeZone(),
  ]);
  const first = pending[0];
  if (!first) return null;
  return (
    <Panel
      className="hidden md:block"
      title={
        <span className="flex items-center gap-2">
          <LoaderCircle
            aria-hidden="true"
            className="size-3.5 shrink-0 animate-spin text-muted-foreground motion-reduce:animate-none"
          />
          {t("pendingTitle", { count: pending.length })}
        </span>
      }
    >
      <p className="text-[0.8125rem] text-muted-foreground">
        {t("pendingBody", {
          map: mapName(first.map),
          time: time(first.played_at, locale, timeZone),
        })}
      </p>
    </Panel>
  );
}

/** The latest session's report and what follows it, or the wait for a first session. */
async function Sessions({ tone }: { tone: Tone }) {
  const [sessions, t, actions] = await Promise.all([
    findSessions(0),
    getTranslations("dashboard"),
    getTranslations("actions"),
  ]);
  // Streamed after the page started: when the API fails, show nothing rather than an error
  // screen, and never the "first session" wait for a player who has sessions.
  if (sessions === null) return null;
  const latest = sessions.items[0];
  const report = latest ? await findSession(latest.id) : null;
  if (latest && !report) return null;

  if (!report) {
    return (
      <>
        <Panel title={t("waiting")} bodyClassName={HEAD_BODY}>
          <p className="max-w-prose text-muted-foreground">{t("waitingLead")}</p>
          <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
            {t("waitingUpload")}
            <Link href="/upload" className={buttonVariants({ variant: "outline", size: "sm" })}>
              {t("waitingUploadLink")}
            </Link>
          </p>
        </Panel>
        <Suspense fallback={null}>
          <PendingPanel />
        </Suspense>
      </>
    );
  }
  // What to work on: the first priority's drills and adjustments this site can describe.
  const first = report.advice[0];
  const known = first
    ? first.args.actions.filter((id) => actions.has(`${id}.title`)).slice(0, 2)
    : [];
  const work = first && known.length > 0 ? first : null;
  const follow = report.follow_up.length > 0;
  const recent = sessions.items.slice(1, 1 + RECENT);
  return (
    <>
      <Latest report={report} tone={tone} />
      {(work || follow) && (
        // Side by side only when both are there: one alone takes the width.
        <div className={cn("grid items-start gap-3 md:gap-4", work && follow && "lg:grid-cols-2")}>
          {work && <WorkOn item={work} known={known} />}
          {follow && <Progress report={report} />}
        </div>
      )}
      {recent.length > 0 && <Recent items={recent} />}
      {/* Nothing while loading: usually nothing to show, and it ends the page, so it moves
          nothing when it comes. */}
      <Suspense fallback={null}>
        <PendingPanel />
      </Suspense>
    </>
  );
}

/**
 * The page while the report loads, laid out as `Sessions` lays out a player with sessions (the
 * common case): the latest session with its figures, three priorities and its button, what to
 * work on and the previous priorities side by side, then the recent sessions on a computer, as their rows.
 */
async function SessionsSkeleton() {
  const t = await getTranslations("dashboard");
  return (
    <>
      <Panel title={t("latest")} bodyClassName={HEAD_BODY}>
        <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-3">
          <div>
            <SkeletonLine className="text-xl md:text-2xl" width="w-52" />
            <SkeletonLine className="mt-1 text-sm" width="w-56" />
          </div>
          <div className="hidden grid-cols-[repeat(4,auto)] gap-x-6 md:grid">
            {slots(4).map((i) => (
              <div key={i} className="leading-tight">
                <SkeletonLine className="text-[0.6875rem]" width="w-14" />
                <SkeletonLine className="text-base" width="w-10" />
                <SkeletonLine className="text-xs" width="w-10" />
              </div>
            ))}
          </div>
        </div>
        <div className="mt-3 md:mt-4">
          {slots(3).map((i) => (
            <div
              key={i}
              className="grid grid-cols-[1.25rem_minmax(0,1fr)] gap-x-3 border-t border-line-soft py-2 md:grid-cols-[1.75rem_minmax(0,1fr)] md:py-2.5"
            >
              <SkeletonLine className="md:text-xl" width="w-3" />
              <div>
                <SkeletonLine className="text-[0.9375rem]" width="w-3/4" />
                <SkeletonLine className="hidden text-[0.8125rem] md:block" width="w-48" />
              </div>
            </div>
          ))}
        </div>
        <Skeleton className="mt-3 h-9 w-full rounded-md md:mt-4 md:w-40" />
      </Panel>
      <div className="grid items-start gap-3 md:gap-4 lg:grid-cols-2">
        <Panel title={t("work")}>
          <SkeletonLine className="hidden text-[0.9375rem] md:block" width="w-36" />
          {slots(2).map((i) => (
            <div key={i} className="py-1.5 md:border-t md:border-line-soft md:py-2.5">
              <SkeletonLine className="text-sm" width="w-48" />
              <SkeletonLine className="mt-0.5 hidden text-sm md:block" width="w-full" />
            </div>
          ))}
        </Panel>
        <Panel title={t("progress")}>
          <SkeletonLine className="mb-2.5 hidden text-[0.8125rem] md:block" width="w-64" />
          <FollowUpSkeleton rows={2} compact />
        </Panel>
      </div>
      <Panel title={t("recent")} className="hidden md:block" flush>
        <SessionRowsHeader />
        <div>
          {slots(RECENT).map((i) => (
            <SessionRowSkeleton key={i} />
          ))}
        </div>
      </Panel>
    </>
  );
}

/**
 * The latest session, the head of the page: its day, size and record with its four key figures,
 * its priorities in order, and the page's one primary action, opening the report. Larger type and
 * the only accent button keep it first.
 */
async function Latest({ report, tone }: { report: SessionReport; tone: Tone }) {
  const [t, sessions, advice, locale, timeZone] = await Promise.all([
    getTranslations("dashboard"),
    getTranslations("sessions"),
    getTranslations("advice"),
    getLocale() as Promise<Locale>,
    getTimeZone(),
  ]);
  const named = await describeReference(report.reference, locale);
  return (
    <Panel
      title={t("latest")}
      aside={
        <span className="hidden tabular-nums md:inline">
          {dateRange(report.started_at, report.ended_at, locale, timeZone)}
        </span>
      }
      bodyClassName={HEAD_BODY}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-3">
        <div>
          <p className="text-xl leading-tight font-semibold md:text-2xl">
            {sessions("titleOf", { date: shortDay(report.started_at, locale, timeZone) })}
          </p>
          <p className="mt-1 flex flex-wrap gap-x-3.5 gap-y-0.5 text-sm text-muted-foreground">
            <span>{sessions("count", { matches: report.matches, rounds: report.rounds })}</span>
            <span className="font-semibold text-foreground tabular-nums">
              {sessions("record", { wins: report.wins, losses: report.losses, ties: report.ties })}
            </span>
          </p>
        </div>
        <Figures
          headlines={report.headlines}
          enough={report.reference.enough}
          className="hidden grid-cols-[repeat(4,auto)] gap-x-6 md:grid"
          valueClassName="text-base"
        />
      </div>
      {report.advice.length === 0 ? (
        <p className="mt-3 border-t border-line-soft pt-3 text-sm text-muted-foreground md:mt-4">
          {report.reference.enough ? advice("none") : advice("noReference")}
        </p>
      ) : (
        <ol className="mt-3 md:mt-4">
          {report.advice.map((item) => (
            <li
              key={item.id}
              className="grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-baseline gap-x-3 border-t border-line-soft py-2 md:grid-cols-[1.75rem_minmax(0,1fr)] md:py-2.5"
            >
              <span className="font-semibold text-muted-foreground tabular-nums md:row-span-2 md:text-xl md:leading-none">
                {item.priority}
              </span>
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
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 md:mt-4">
        <Link
          href={`/sessions/${encodeURIComponent(report.id)}`}
          className={cn(buttonVariants(), "w-full md:w-auto")}
        >
          {t("openReport")}
        </Link>
        {named.short && (
          <p className="hidden text-[0.8125rem] text-muted-foreground md:block">
            {sessions("referenceLabel", { reference: named.short })}
          </p>
        )}
      </div>
    </Panel>
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

/** The first priority's drills and adjustments (`known`: those this site can describe). */
async function WorkOn({ item, known }: { item: Advice; known: string[] }) {
  const [t, advice, actions] = await Promise.all([
    getTranslations("dashboard"),
    getTranslations("advice"),
    getTranslations("actions"),
  ]);
  return (
    <Panel title={t("work")} aside={<span className="hidden md:inline">{t("workLead")}</span>}>
      <p className="hidden text-[0.9375rem] font-semibold md:block">
        {advice(`rules.${item.rule_id}.label`)}
      </p>
      <ul className="md:mt-1">
        {known.map((id) => {
          const kind = id.split(".")[0] ?? "";
          const Icon = kind === "drill" ? Dumbbell : Compass;
          return (
            <li
              key={id}
              className="grid grid-cols-[1rem_minmax(0,1fr)] gap-x-2.5 py-1.5 md:border-t md:border-line-soft md:py-2.5 md:last:pb-0"
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
    </Panel>
  );
}

/** The previous priorities, over the last sessions. */
async function Progress({ report }: { report: SessionReport }) {
  const [t, locale] = await Promise.all([
    getTranslations("dashboard"),
    getLocale() as Promise<Locale>,
  ]);
  return (
    <Panel title={t("progress")}>
      <p className="mb-2.5 hidden text-[0.8125rem] text-muted-foreground md:block">
        {t("progressLead")}
      </p>
      <FollowUpList items={report.follow_up} locale={locale} compact />
    </Panel>
  );
}

/** The sessions before the latest, as rows of the session list (a computer only). */
async function Recent({ items }: { items: SessionSummary[] }) {
  const t = await getTranslations("dashboard");
  return (
    <Panel
      title={t("recent")}
      aside={
        <Link
          href="/sessions"
          className={cn(buttonVariants({ variant: "link" }), "h-auto text-xs")}
        >
          {t("allSessions")}
        </Link>
      }
      className="hidden md:block"
      flush
    >
      <SessionRowsHeader />
      <ul>
        {items.map((session) => (
          <SessionRow key={session.id} session={session} />
        ))}
      </ul>
    </Panel>
  );
}
