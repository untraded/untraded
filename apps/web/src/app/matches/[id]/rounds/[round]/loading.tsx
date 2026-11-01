// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { Loading, Skeleton, SkeletonLine, slots } from "@/components/skeleton";

/**
 * A round's page while it loads: the breadcrumb, the round's title and result with the previous
 * and next buttons, then the viewer as it is laid out (the square map with its controls, the two
 * sides beside it on a computer and below it on a phone).
 */
export default function RoundLoading() {
  return (
    <Loading className="flex flex-col gap-3.5">
      <SkeletonLine className="text-[0.8125rem]" width="w-72" />
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2.5">
        <div className="flex flex-col gap-1">
          <SkeletonLine className="text-2xl" width="w-40" />
          <SkeletonLine className="text-sm" width="w-56" />
        </div>
        <div className="flex gap-1.5">
          <Skeleton className="h-7 w-24 rounded-sm" />
          <Skeleton className="h-7 w-24 rounded-sm" />
        </div>
      </div>
      <div className="grid gap-3.5 lg:grid-cols-[minmax(0,calc(100dvh-12rem))_18.5rem] lg:items-start">
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <Skeleton className="aspect-square w-full rounded-none" />
          <div className="flex items-center gap-3.5 border-t border-border px-3 py-2.5">
            <Skeleton className="h-7 w-24 rounded-sm" />
            <Skeleton className="h-1 flex-1 rounded-full" />
            <Skeleton className="hidden h-7 w-28 rounded-sm sm:block" />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-1 lg:gap-3">
          {[0, 1].map((side) => (
            <div key={side} className="rounded-lg border border-border bg-card">
              <div className="border-b border-line-soft px-3 py-2">
                <SkeletonLine className="text-[0.8125rem]" width="w-20" />
              </div>
              <div className="flex flex-col gap-2 px-3 py-2.5">
                {slots(5).map((i) => (
                  <SkeletonLine key={i} className="text-[0.8125rem]" width="w-full" />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Loading>
  );
}
