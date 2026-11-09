// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import { Loading, Skeleton, SkeletonLine, slots } from "@/components/skeleton";

/** Rows of the two periods drawn while loading (a recent day, then the rest of the week). */
const PERIODS = [3, 5];

/**
 * The match list while it loads: the title and the upload button, then a panel per period (its
 * band with the period and its record, the column names on wide screens, then its rows). A row is
 * two lines on a phone (map and score, then when and K–D) and one line on wide screens, as on the
 * page. Same band as `Panel`.
 */
export default async function MatchesLoading() {
  const t = await getTranslations("matches");
  return (
    <Loading className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
        <Skeleton className="h-9 w-40 rounded-md" />
      </div>
      {PERIODS.map((rows) => (
        <div key={rows} className="rounded-lg border border-border bg-card">
          <div className="flex min-h-10 items-center justify-between gap-x-3 rounded-t-[3px] border-b border-border bg-panel-head px-3.5 py-1.5">
            <SkeletonLine className="text-[0.8125rem]" width="w-24" />
            <SkeletonLine className="text-xs" width="w-32" />
          </div>
          <div className="hidden border-b border-line-soft px-4 py-1.5 text-xs lg:block">
            <SkeletonLine width="w-full" />
          </div>
          <div>
            {slots(rows).map((i) => (
              <div
                key={i}
                className="border-t border-line-soft px-3.5 py-2.5 first:border-t-0 lg:px-4 lg:py-2"
              >
                <div className="flex justify-between gap-3">
                  <SkeletonLine width="w-28" />
                  <SkeletonLine width="w-16" />
                </div>
                <div className="mt-1 flex justify-between gap-3 text-xs lg:hidden">
                  <SkeletonLine width="w-24" />
                  <SkeletonLine width="w-20" />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </Loading>
  );
}
