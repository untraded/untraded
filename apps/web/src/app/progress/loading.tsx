// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import { FollowUpSkeleton } from "@/components/follow-up";
import { Loading, Skeleton, SkeletonLine } from "@/components/skeleton";
import { KEY_FIGURES } from "@/lib/progress";

/**
 * The progress page while it loads: the title and its lead, the periods and the legend, the four
 * key-figure cards (name, latest value, then the curve at its drawn proportions: narrow below the
 * card's `@md`, wide above: `NARROW` or `WIDE` by `H` in `@/lib/progress`), then the previous
 * priorities.
 */
export default async function ProgressLoading() {
  const t = await getTranslations("progress");
  return (
    <Loading className="flex flex-col gap-5">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
        <p className="max-w-prose text-sm text-muted-foreground">{t("lead")}</p>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Skeleton className="h-8 w-80 max-w-full rounded-md" />
        <SkeletonLine className="text-[0.8125rem]" width="w-48" />
        <span aria-hidden="true" className="flex gap-3.5 text-xs text-muted-foreground sm:ml-auto">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-4 border-t-2 border-foreground" />
            {t("you")}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-4 border-t-2 border-dashed border-muted-foreground" />
            {t("reference")}
          </span>
        </span>
      </div>

      <div className="grid gap-3.5 md:grid-cols-2">
        {KEY_FIGURES.map((id) => (
          <div
            key={id}
            className="@container rounded-lg border border-border bg-card px-4 pt-3.5 pb-2.5"
          >
            <div className="flex justify-between gap-x-3">
              <SkeletonLine width="w-24" />
              <SkeletonLine className="text-[0.8125rem]" width="w-20" />
            </div>
            <div className="flex items-baseline justify-between gap-x-3">
              <SkeletonLine className="text-2xl" width="w-16" />
              <SkeletonLine className="text-[0.8125rem]" width="w-28" />
            </div>
            <div className="mt-1">
              <div className="h-5" />
              <Skeleton className="aspect-[340/210] @md:aspect-[520/210]" />
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold text-muted-foreground">{t("priorities")}</h2>
        <div className="rounded-lg border border-border bg-card p-4">
          <FollowUpSkeleton rows={1} />
        </div>
      </div>
    </Loading>
  );
}
