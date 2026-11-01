// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { Skeleton, SkeletonLine, slots } from "@/components/skeleton";

/**
 * The parts of the match page while they load, each with the real part's paddings, text sizes
 * and row counts, so nothing moves when the real one replaces it.
 */

/** A section title above a part (`text-[0.8125rem]`, like the real ones). */
function Title({ width = "w-28" }: { width?: string }) {
  return <SkeletonLine className="text-[0.8125rem]" width={width} />;
}

/** The match's rounds: one row per half on a phone, the whole match on one row on wider screens
 * (24 rounds, the length of a regulation match). */
export function RoundsSkeleton() {
  const half = slots(12).map((i) => i);
  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-between gap-x-4">
        <Title width="w-16" />
        <SkeletonLine className="hidden text-[0.8125rem] sm:block" width="w-72" />
      </div>
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
    </div>
  );
}

/**
 * The priorities of the match's session. The real part is always there for a player of the
 * match, but is often only its title and a one-line box ("no priority touches this match", or no
 * session yet): the placeholder takes that smallest size. A match with flagged rounds then grows
 * by its rows, below the rounds already in place, rather than leaving a tall empty block over the
 * rating when it has none.
 */
export function PrioritiesSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      <Title width="w-40" />
      <div className="rounded-md border border-border bg-card p-4">
        <SkeletonLine className="text-sm" width="w-64" />
      </div>
    </div>
  );
}

/** The rating card: the value, the level, the parts as bars, the hint. */
export function RatingSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-between gap-x-3">
        <Title width="w-36" />
        <Title width="w-16" />
      </div>
      <div className="flex flex-col gap-3 rounded-md border border-border bg-card px-4 py-3.5">
        <SkeletonLine className="text-3xl" width="w-20" />
        <SkeletonLine className="text-sm" width="w-48" />
        <div className="flex flex-col gap-1.5">
          {slots(6).map((i) => (
            <div
              key={i}
              className="grid grid-cols-[6.5rem_minmax(0,1fr)_3.5rem] items-center gap-x-3 text-sm"
            >
              <SkeletonLine width="w-20" />
              <Skeleton className="h-2.5" />
              <SkeletonLine className="text-right" width="w-10" />
            </div>
          ))}
        </div>
        <SkeletonLine className="text-xs" width="w-72" />
      </div>
    </div>
  );
}

/** The player's numbers by side: a two-line head, then seven rows. */
export function SidesSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      <Title width="w-20" />
      <div className="overflow-hidden rounded-md border border-border bg-card text-sm">
        <div className="flex justify-end gap-6 px-4 py-2 text-xs">
          {[0, 1].map((i) => (
            <div key={i} className="w-18">
              <SkeletonLine className="text-right" width="w-6" />
              <SkeletonLine className="text-right" width="w-16" />
            </div>
          ))}
        </div>
        {slots(7).map((i) => (
          <div key={i} className="flex justify-between gap-3 border-t border-line-soft px-4 py-2">
            <SkeletonLine width="w-24" />
            <SkeletonLine width="w-36" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** One team: its name and score, the column names, five players. */
export function TeamSkeleton() {
  return (
    <div className="rounded-md border border-border bg-card">
      <div className="flex items-center justify-between gap-3 px-3 py-2">
        <SkeletonLine className="text-sm" width="w-36" />
        <SkeletonLine className="text-lg" width="w-6" />
      </div>
      <div className="border-t border-border px-3 py-1.5">
        <SkeletonLine className="text-xs" width="w-full" />
      </div>
      {slots(5).map((i) => (
        <div
          key={i}
          className="flex justify-between gap-3 border-t border-line-soft px-3 py-1.5 text-[0.8125rem]"
        >
          <SkeletonLine width="w-28" />
          <SkeletonLine width="w-32" />
        </div>
      ))}
    </div>
  );
}
