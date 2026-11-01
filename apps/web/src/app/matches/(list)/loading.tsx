// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import { Loading, Skeleton, SkeletonLine, slots } from "@/components/skeleton";

/** Rows of the two periods drawn while loading (a recent day, then the rest of the week). */
const PERIODS = [3, 5];

/**
 * The match list while it loads: the title and the upload button, then periods of rows. A row is
 * two lines on a phone (map and score, then when and K–D) and one line on wide screens, with the
 * column names above the first period, as on the page.
 */
export default async function MatchesLoading() {
  const t = await getTranslations("matches");
  return (
    <Loading className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
        <Skeleton className="h-9 w-40 rounded-md" />
      </div>
      {PERIODS.map((rows, index) => (
        <div key={rows}>
          <div className="mb-2 flex justify-between gap-x-3 text-sm">
            <SkeletonLine width="w-24" />
            <SkeletonLine width="w-36" />
          </div>
          <div className="rounded-lg border border-border bg-card">
            {index === 0 && (
              <div className="hidden border-b border-border px-4 py-2 text-xs lg:block">
                <SkeletonLine width="w-full" />
              </div>
            )}
            <div>
              {slots(rows).map((i) => (
                <div
                  key={i}
                  className="border-t border-line-soft px-3.5 py-2.5 first:border-t-0 lg:px-4"
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
        </div>
      ))}
    </Loading>
  );
}
