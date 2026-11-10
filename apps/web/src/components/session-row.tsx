// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { MapChips } from "@/components/map-chips";
import { SkeletonLine, slots } from "@/components/skeleton";
import type { Locale } from "@/i18n/locale";
import type { Comparison, SessionSummary } from "@/lib/api";
import { cn } from "@/lib/cn";
import {
  delta,
  gap,
  gapTrend,
  hours,
  mapName,
  metric,
  type Trend,
  trendClass,
  weekdayDay,
} from "@/lib/format";

/** The four key figures of a session, in this order: the same in every list and on the home. */
export const FIGURES = [
  { id: "rating.untraded", label: "urating" },
  { id: "base.adr", label: "adr" },
  { id: "base.kast", label: "kast" },
  { id: "trade.untraded_deaths", label: "untraded" },
] as const;

/** The name of a figure: the session context's own words, and the untraded deaths per round
 * (the basis the sessions compare them on), said so on screen. */
function figureName(
  t: Awaited<ReturnType<typeof getTranslations<"sessions">>>,
  label: (typeof FIGURES)[number]["label"],
): string {
  return label === "untraded" ? t("figures.untraded") : t(`context.${label}`);
}

/** Whether a figure has a gap to show: a reference, and its difference. */
function hasGap(c: Comparison | undefined, enough: boolean): boolean {
  return !!c && enough && c.reference !== null && c.delta !== null;
}

const ARROW: Record<Trend, string> = { better: "▲", worse: "▼", same: "=" };
const TREND_WORD: Record<Trend, "better" | "worse" | "stable"> = {
  better: "better",
  worse: "worse",
  same: "stable",
};

/**
 * The columns of a session row from `xl`: the day, the record with its maps, the four figures, the
 * chevron. Below `xl` a row stacks, its figures in a row of four.
 */
const COLUMNS = "xl:grid-cols-[7.5rem_minmax(0,1fr)_repeat(4,5.75rem)_1rem]";

/**
 * The header of the figures' columns, drawn from `xl` above a list of `SessionRow`s. Hidden from
 * assistive technologies: each figure carries its own name.
 */
export async function SessionRowsHeader() {
  const t = await getTranslations("sessions");
  return (
    <div
      aria-hidden="true"
      className={cn(
        "hidden items-end gap-x-4 border-b border-line-soft px-3.5 py-1.5 text-[0.6875rem] leading-tight text-muted-foreground xl:grid",
        COLUMNS,
      )}
    >
      {FIGURES.map(({ id, label }, i) => (
        <span
          key={id}
          translate={label === "untraded" ? undefined : "no"}
          className={cn("text-right", i === 0 && "col-start-3")}
        >
          {figureName(t, label)}
        </span>
      ))}
    </div>
  );
}

/**
 * One session in a list, as a link to its report: the day and hours, the record and the maps
 * with their result on one line, then the four key figures with their signed gap to the
 * reference (an arrow and the word for assistive technologies, never the colour alone).
 */
export async function SessionRow({ session }: { session: SessionSummary }) {
  const [t, results, locale, timeZone] = await Promise.all([
    getTranslations("sessions"),
    getTranslations("result"),
    getLocale() as Promise<Locale>,
    getTimeZone(),
  ]);
  const record =
    session.wins > session.losses ? "better" : session.losses > session.wins ? "worse" : "same";
  return (
    <li className="group border-t border-line-soft first:border-t-0">
      <Link
        href={`/sessions/${encodeURIComponent(session.id)}`}
        className={cn(
          "grid grid-cols-[minmax(0,1fr)_1rem] gap-x-3 gap-y-2 px-3.5 py-2.5 hover:bg-muted group-last:rounded-b-lg xl:items-center xl:gap-x-4",
          COLUMNS,
        )}
      >
        <span className="flex flex-wrap items-baseline gap-x-2 xl:block">
          <span className="text-sm font-semibold xl:block">
            {weekdayDay(session.started_at, locale, timeZone)}
          </span>
          <span className="text-xs text-muted-foreground tabular-nums">
            {hours(session.started_at, session.ended_at, locale, timeZone)}
          </span>
        </span>
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-2.5 gap-y-1 overflow-x-clip text-[0.8125rem]">
          <span className={cn("shrink-0 text-sm font-semibold tabular-nums", trendClass(record))}>
            {t("record", { wins: session.wins, losses: session.losses, ties: session.ties })}
          </span>
          <ul aria-label={t("mapsPlayed")} className="sr-only">
            {session.maps.map((played) => (
              <li key={played.match_id}>
                {played.result && `${results(played.result)}, `}
                <span translate="no">{mapName(played.map)}</span>
                {played.my_score !== null &&
                  played.their_score !== null &&
                  `, ${played.my_score}–${played.their_score}`}
              </li>
            ))}
          </ul>
          <MapChips maps={session.maps} t={t} />
        </div>
        <Figures
          headlines={session.headlines}
          enough={session.enough}
          className="grid grid-cols-4 gap-x-3 xl:contents"
          cellClassName="xl:text-right"
          nameClassName="xl:sr-only"
        />
        <ChevronRight
          aria-hidden="true"
          className="col-start-2 row-span-3 row-start-1 size-4 self-center text-muted-foreground xl:col-start-7 xl:row-span-1"
        />
      </Link>
    </li>
  );
}

/**
 * The four key figures of a session as a description list: each name, its value and, against a
 * reference, its signed gap with an arrow in the colour of the trend (and the trend in words for
 * assistive technologies). A figure the session lacks reads as a dash, so columns stay aligned.
 */
export async function Figures({
  headlines,
  enough,
  className,
  cellClassName,
  nameClassName,
  valueClassName = "text-sm",
}: {
  headlines: Comparison[];
  enough: boolean;
  className?: string;
  cellClassName?: string;
  nameClassName?: string;
  valueClassName?: string;
}) {
  const [t, locale] = await Promise.all([
    getTranslations("sessions"),
    getLocale() as Promise<Locale>,
  ]);
  return (
    <dl className={className}>
      {FIGURES.map(({ id, label }) => {
        const c = headlines.find((h) => h.metric_id === id);
        const moved = c ? gapTrend(gap(c)) : "same";
        return (
          <div key={id} className={cn("grid content-end leading-tight", cellClassName)}>
            <dt
              translate={label === "untraded" ? undefined : "no"}
              className={cn("text-[0.6875rem] text-muted-foreground", nameClassName)}
            >
              {figureName(t, label)}
            </dt>
            <dd className={cn("font-semibold tabular-nums", valueClassName)}>
              {c ? metric(c.session, c.unit, c.basis, locale) : "—"}
            </dd>
            <dd
              aria-hidden={hasGap(c, enough) ? undefined : true}
              className={cn("text-xs tabular-nums", trendClass(moved))}
            >
              {c && hasGap(c, enough) ? (
                <>
                  <span aria-hidden="true">{ARROW[moved]}</span>{" "}
                  <span className="sr-only">{t("context.gap")} </span>
                  {delta(c.delta, c.unit, c.basis, locale)}
                  <span className="sr-only"> ({t(TREND_WORD[moved])})</span>
                </>
              ) : (
                // Keeps the rows the same height when a figure has no reference.
                <span className="invisible">{ARROW.same}</span>
              )}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

/** A session row on its way, laid out as `SessionRow` (with its figures' names below `xl`). Put
 * the rows in their own container, as the real rows are in their list, so the first has no rule. */
export function SessionRowSkeleton() {
  return (
    <div
      className={cn(
        "grid gap-y-2 border-t border-line-soft py-2.5 pr-[2.625rem] pl-3.5 first:border-t-0 xl:items-center xl:gap-x-4 xl:pr-[2.875rem]",
        "xl:grid-cols-[7.5rem_minmax(0,1fr)_repeat(4,5.75rem)]",
      )}
    >
      <div className="flex items-baseline gap-x-2 xl:block">
        <SkeletonLine className="text-sm" width="w-24" />
        <SkeletonLine className="text-xs" width="w-20" />
      </div>
      <SkeletonLine className="text-sm" width="w-56" />
      <div className="grid grid-cols-4 gap-x-3 xl:contents">
        {slots(4).map((j) => (
          <div key={j} className="leading-tight xl:grid xl:justify-items-end">
            <SkeletonLine className="text-[0.6875rem] xl:hidden" width="w-12" />
            <SkeletonLine className="text-[0.6875rem] xl:hidden" width="w-8" />
            {/* The last name, the longest, wraps to a third line on a phone. */}
            {j === "slot-3" && <SkeletonLine className="text-[0.6875rem] xl:hidden" width="w-8" />}
            <SkeletonLine className="text-sm" width="w-10" />
            <SkeletonLine className="text-xs" width="w-10" />
          </div>
        ))}
      </div>
    </div>
  );
}
