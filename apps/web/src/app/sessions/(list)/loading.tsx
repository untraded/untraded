// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import { Loading, SkeletonLine, slots } from "@/components/skeleton";

/** Rows of the two weeks drawn while loading. */
const WEEKS = [2, 3];

/**
 * The session list while it loads: the title and its lead, then weeks of rows. A row is the day
 * and hours, the record and maps with the first priority, then the two key figures: stacked on a
 * phone, in three columns from `md`, as on the page.
 */
export default async function SessionsLoading() {
  const t = await getTranslations("sessions");
  return (
    <Loading className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">{t("lead")}</p>
      </div>
      {WEEKS.map((rows) => (
        <div key={rows}>
          <div className="mb-2 flex justify-between gap-x-3 text-sm">
            <SkeletonLine width="w-28" />
            <SkeletonLine width="w-40" />
          </div>
          <div className="rounded-lg border border-border bg-card">
            {slots(rows).map((i) => (
              <div
                key={i}
                className="grid gap-y-1.5 border-t border-line-soft py-3 pr-10 pl-3.5 first:border-t-0 md:grid-cols-[7.5rem_minmax(0,1fr)_15.5rem] md:items-center md:gap-x-4 md:pr-12 md:pl-4"
              >
                <div className="flex items-baseline gap-x-2 md:block">
                  <SkeletonLine width="w-24" />
                  <SkeletonLine className="text-xs" width="w-20" />
                </div>
                <div className="min-w-0">
                  <SkeletonLine className="text-sm" width="w-56" />
                  <SkeletonLine className="mt-1 text-[0.8125rem]" width="w-64" />
                </div>
                <div className="grid grid-cols-2 gap-x-4 text-[0.8125rem]">
                  <SkeletonLine width="w-full" />
                  <SkeletonLine width="w-full" />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </Loading>
  );
}
