// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import { SessionRowSkeleton, SessionRowsHeader } from "@/components/session-row";
import { Loading, SkeletonLine, slots } from "@/components/skeleton";

/** Rows of the two weeks drawn while loading. */
const WEEKS = [2, 3];

/**
 * The session list while it loads: the title and its lead, then weeks as panels (a band with the
 * week and its summary, then rows). A row is the day and hours, the record and maps with the
 * first priority, then the four key figures: stacked on a phone, in columns from `xl`, as on the
 * page.
 */
export default async function SessionsLoading() {
  const t = await getTranslations("sessions");
  return (
    <Loading className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">{t("lead")}</p>
      </div>
      {WEEKS.map((rows) => (
        <div key={rows} className="rounded-lg border border-border bg-card">
          <div className="flex min-h-10 items-center justify-between gap-x-3 rounded-t-[3px] border-b border-border bg-panel-head px-3.5 py-1.5">
            <SkeletonLine className="text-[0.8125rem]" width="w-28" />
            <SkeletonLine className="text-xs" width="w-32" />
          </div>
          <SessionRowsHeader />
          <div>
            {slots(rows).map((i) => (
              <SessionRowSkeleton key={i} />
            ))}
          </div>
        </div>
      ))}
    </Loading>
  );
}
