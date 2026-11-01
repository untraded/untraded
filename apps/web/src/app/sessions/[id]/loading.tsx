// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { Loading, Skeleton, SkeletonLine, slots } from "@/components/skeleton";

/** A box of the report's side column: its title, then `rows` rows of two lines. */
function Box({ rows }: { rows: number }) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3.5">
      <SkeletonLine className="mb-2.5 text-sm" width="w-28" />
      <div>
        {slots(rows).map((i) => (
          <div key={i} className="border-t border-line-soft py-2 first:border-t-0 first:pt-0">
            <div className="flex items-center justify-between gap-2.5">
              <SkeletonLine className="text-[0.8125rem]" width="w-24" />
              <SkeletonLine className="text-xl leading-tight" width="w-14" />
            </div>
            <SkeletonLine className="text-xs" width="w-40" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** A priority's summary: its number, finding and cost. */
function Summary() {
  return (
    <div className="grid grid-cols-[1.25rem_minmax(0,1fr)] gap-x-3 gap-y-0.5 p-4 sm:px-5">
      <SkeletonLine className="text-[1.0625rem]" width="w-3" />
      <SkeletonLine className="text-base leading-snug sm:text-[1.0625rem]" width="w-3/4" />
      <SkeletonLine className="col-start-2 text-[0.8125rem]" width="w-48" />
    </div>
  );
}

/** A priority folded, as the second and third are. */
function Folded() {
  return (
    <div className="rounded-lg border border-border bg-card">
      <Summary />
    </div>
  );
}

/**
 * A session report while it loads: the header (title, dates and record, reference), then the
 * priorities (the first one open: its rounds and what to do) beside the key figures and the
 * matches, then the metrics. Same columns and paddings as `Report`.
 */
export default async function SessionLoading() {
  const t = await getTranslations("sessions");
  const advice = await getTranslations("advice");
  return (
    <Loading className="flex flex-col gap-7">
      <div className="flex flex-col gap-2.5">
        <Link href="/sessions" className="text-sm text-muted-foreground hover:text-foreground">
          ← {t("back")}
        </Link>
        <SkeletonLine className="text-2xl leading-tight sm:text-[1.75rem]" width="w-64" />
        <SkeletonLine className="text-[0.9375rem]" width="w-80" />
        <SkeletonLine className="text-sm" width="w-full max-w-[36rem]" />
      </div>

      <div className="grid items-start gap-7 lg:grid-cols-[minmax(0,1fr)_18.75rem]">
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">{advice("title")}</h2>
            <Skeleton className="h-8 w-40 rounded-md" />
          </div>
          <div className="rounded-lg border border-border bg-card">
            <Summary />
            <div className="flex flex-col gap-5 px-4 pb-4 sm:pr-5 sm:pl-12">
              <div className="flex flex-col gap-3">
                <SkeletonLine className="text-[0.8125rem]" width="w-32" />
                <SkeletonLine className="text-sm" width="w-40" />
                <Skeleton className="h-[26px]" />
                <Skeleton className="h-8 w-64 max-w-full rounded-md" />
              </div>
              <div className="flex flex-col gap-3">
                <SkeletonLine className="text-[0.8125rem]" width="w-28" />
                {[0, 1].map((i) => (
                  <div key={i}>
                    <SkeletonLine width="w-48" />
                    <SkeletonLine className="mt-0.5 text-sm" width="w-full max-w-prose" />
                  </div>
                ))}
              </div>
            </div>
          </div>
          <Folded />
          <Folded />
        </div>
        <div className="flex flex-col gap-3.5">
          <Box rows={4} />
          <Box rows={3} />
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <div>
          <h2 className="text-lg font-semibold">{t("allMetrics")}</h2>
          <SkeletonLine className="mt-0.5 text-sm" width="w-96" />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {slots(6).map((i) => (
            <Skeleton key={i} className="h-7 w-20 rounded-md" />
          ))}
        </div>
        <Skeleton className="h-64 rounded-lg" />
      </div>
    </Loading>
  );
}
