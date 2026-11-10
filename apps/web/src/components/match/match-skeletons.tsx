// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { ReactNode } from "react";
import { Skeleton, SkeletonLine, slots } from "@/components/skeleton";
import { cn } from "@/lib/cn";

/**
 * The parts of the match page while they load, each with the real part's band, paddings, text
 * sizes and row counts, so nothing moves when the real one replaces it.
 */

/** A panel's frame while it loads: the title band (the title known or a placeholder, and a
 * placeholder at its right), then the body. Same band and paddings as `Panel`. */
function PanelFrame({
  title,
  aside = "w-24",
  asideClassName,
  flush = false,
  bodyClassName,
  children,
}: {
  /** Classes of the placeholder's line itself (its place in the band). */
  asideClassName?: string;
  title?: string;
  /** The width classes of the placeholder at the band's right; `null` for none. */
  aside?: string | null;
  flush?: boolean;
  bodyClassName?: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="flex min-h-10 flex-wrap items-center justify-between gap-x-3 gap-y-1 rounded-t-[3px] border-b border-border bg-panel-head px-3.5 py-1.5">
        {title ? (
          <h2 className="text-[0.8125rem] font-semibold">{title}</h2>
        ) : (
          <SkeletonLine className="text-[0.8125rem]" width="w-28" />
        )}
        {aside && <SkeletonLine className={cn("text-xs", asideClassName)} width={aside} />}
      </div>
      <div className={cn(!flush && "px-3.5 py-3", bodyClassName)}>{children}</div>
    </div>
  );
}

/** The match's rounds: one row per half on a phone, the whole match on one row on wider screens
 * (24 rounds, the length of a regulation match). */
export function RoundsSkeleton({ title }: { title?: string }) {
  const half = slots(12);
  return (
    // On a phone the legend takes a line of its own under the title, as the real one does.
    <PanelFrame
      title={title}
      aside="w-72 max-w-full"
      asideClassName="basis-full sm:basis-auto"
      bodyClassName="flex flex-col gap-2.5"
    >
      <div className="flex flex-col gap-1.5 sm:hidden">
        {[0, 1].map((h) => (
          <div key={h} className="flex flex-col gap-0.5">
            <SkeletonLine className="text-[0.6875rem]" width="w-5" />
            <div className="grid grid-cols-12 gap-0.5">
              {half.map((i) => (
                <Skeleton key={i} className="h-[26px] rounded-[2px]" />
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="hidden flex-col gap-1 sm:flex">
        <SkeletonLine className="text-[0.6875rem]" width="w-5" />
        <div className="flex gap-1.5">
          {[0, 1].map((h) => (
            <div key={h} className="grid flex-1 grid-cols-12 gap-[3px]">
              {half.map((i) => (
                <Skeleton key={i} className="h-[26px] rounded-[2px]" />
              ))}
            </div>
          ))}
        </div>
      </div>
      <SkeletonLine className="text-xs" width="w-40" />
    </PanelFrame>
  );
}

/**
 * What to review: the priorities of the match's session that touch the match. The real panel is
 * often only its band and one line ("no priority touches this match", or no session yet): the
 * placeholder takes that smallest size, and a match with flagged rounds grows by its rows.
 */
export function ReviewSkeleton({ title }: { title?: string }) {
  return (
    <PanelFrame title={title}>
      <SkeletonLine className="text-sm" width="w-64 max-w-full" />
    </PanelFrame>
  );
}

/**
 * The match against the player's previous matches: five rows (name, value and mean, ruler, word
 * and gap; the ruler and the word under them on a phone), then the legend. Same grid as
 * `SelfNorm`. The title waits for the count of previous matches.
 */
export function SelfNormSkeleton() {
  return (
    <PanelFrame aside="w-12" flush>
      {slots(5).map((i) => (
        <div
          key={i}
          className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 border-t border-line-soft px-3.5 py-2 first:border-t-0 sm:grid-cols-[minmax(6.5rem,1fr)_4.5rem_minmax(8rem,2fr)_7.25rem]"
        >
          <SkeletonLine className="text-sm leading-tight" width="w-24" />
          <div className="flex flex-col items-end leading-tight">
            <SkeletonLine className="leading-tight" width="w-10" />
            <SkeletonLine className="text-xs" width="w-14" />
          </div>
          <Skeleton className="col-span-2 mx-2 my-[9px] h-2.5 sm:col-span-1" />
          <div className="col-span-2 flex gap-1.5 text-xs leading-tight sm:col-span-1 sm:block">
            <SkeletonLine width="w-20" />
            <SkeletonLine width="w-10" />
          </div>
        </div>
      ))}
      <div className="flex flex-col gap-1.5 border-t border-line-soft px-3.5 py-2 text-xs">
        <SkeletonLine width="w-72 max-w-full" />
        <SkeletonLine width="w-full" />
      </div>
    </PanelFrame>
  );
}

/** The rating panel: the value, the level, the parts as bars, the hint. */
export function RatingSkeleton({ title }: { title?: string }) {
  return (
    <PanelFrame title={title} aside="w-16" bodyClassName="flex flex-col gap-3">
      <SkeletonLine className="text-3xl" width="w-20" />
      <SkeletonLine className="text-sm" width="w-48" />
      <div className="flex flex-col gap-1.5">
        {slots(6).map((i) => (
          <div
            key={i}
            className="grid grid-cols-[6.5rem_minmax(0,1fr)_3.5rem] sm:grid-cols-[9rem_minmax(0,1fr)_3.5rem] items-center gap-x-3 text-sm"
          >
            <SkeletonLine width="w-20" />
            <Skeleton className="h-2.5" />
            <SkeletonLine className="text-right" width="w-10" />
          </div>
        ))}
      </div>
      <SkeletonLine className="text-xs" width="w-72 max-w-full" />
    </PanelFrame>
  );
}

/** The player's numbers by side: a two-line head, then seven rows, edge to edge. */
export function SidesSkeleton({ title }: { title?: string }) {
  return (
    <PanelFrame title={title} aside={null} flush bodyClassName="text-sm">
      <div className="flex justify-end gap-6 px-3.5 py-2 text-xs">
        {[0, 1].map((i) => (
          <div key={i} className="w-18">
            <SkeletonLine className="text-right" width="w-6" />
            <SkeletonLine className="text-right" width="w-16" />
          </div>
        ))}
      </div>
      {slots(7).map((i) => (
        <div key={i} className="flex justify-between gap-3 border-t border-line-soft px-3.5 py-2">
          <SkeletonLine width="w-24" />
          <SkeletonLine width="w-36" />
        </div>
      ))}
    </PanelFrame>
  );
}

/** One team: its band (name, score), the column names, five players, edge to edge. */
export function TeamSkeleton() {
  return (
    <PanelFrame aside="w-6" flush bodyClassName="text-[0.8125rem]">
      <div className="px-3.5 py-1.5">
        <SkeletonLine className="text-xs" width="w-full" />
      </div>
      {slots(5).map((i) => (
        <div key={i} className="flex justify-between gap-3 border-t border-line-soft px-3.5 py-1.5">
          <SkeletonLine width="w-28" />
          <SkeletonLine width="w-32" />
        </div>
      ))}
    </PanelFrame>
  );
}
