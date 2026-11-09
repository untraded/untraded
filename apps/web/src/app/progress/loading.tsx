// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { FollowUpSkeleton } from "@/components/follow-up";
import { Legend } from "@/components/progress/legend";
import { Loading, Skeleton, SkeletonLine } from "@/components/skeleton";
import { ContextBar } from "@/components/ui/context-bar";
import { cn } from "@/lib/cn";
import { KEY_FIGURES } from "@/lib/progress";

/** The short names the lists use for the key figures (`matches`), as on the page. */
const NAMES: Record<(typeof KEY_FIGURES)[number], string> = {
  "rating.untraded": "urating",
  "base.adr": "adr",
  "base.kast": "kast",
  "trade.untraded_deaths": "untraded",
};

/** A panel's frame while it loads: its title band (the title known), then the body. Same band as
 * `Panel`. */
function PanelFrame({
  title,
  className,
  children,
}: {
  title: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("rounded-lg border border-border bg-card", className)}>
      {/* Wraps like the band of `Panel`: the change sentence may drop under the title. */}
      <div className="flex min-h-10 flex-wrap items-center justify-between gap-x-3 gap-y-1 rounded-t-[3px] border-b border-border bg-panel-head px-3.5 py-1.5">
        <h2 className="text-[0.8125rem] font-semibold">{title}</h2>
        <SkeletonLine className="text-xs" width="w-52" />
      </div>
      {children}
    </div>
  );
}

/**
 * The progress page while it loads: the context bar (the periods, the sessions they hold, the
 * legend), the title and its lead, the four key-figure panels (latest value, then the curve at
 * its drawn proportions: narrow below the panel's `@md`, wide above: `NARROW` or `WIDE` by `H` in
 * `@/lib/progress`), then the previous priorities.
 */
export default async function ProgressLoading() {
  const t = await getTranslations("progress");
  const m = await getTranslations("matches");
  return (
    <>
      <ContextBar label={t("context")}>
        <Skeleton className="h-8 w-72 max-w-full shrink-0 rounded-sm xl:h-7 xl:w-64" />
        <SkeletonLine className="text-[0.8125rem]" width="w-48" />
        <Legend you={t("you")} reference={t("reference")} />
      </ContextBar>
      <Loading className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
          <p className="max-w-prose text-sm text-muted-foreground">{t("lead")}</p>
        </div>

        <div className="grid gap-3.5 md:grid-cols-2">
          {KEY_FIGURES.map((id) => (
            <PanelFrame key={id} title={m(NAMES[id])} className="@container">
              <div className="px-3.5 pt-2.5 pb-2">
                <div className="flex items-baseline justify-between gap-x-3">
                  <SkeletonLine className="text-2xl" width="w-16" />
                  <SkeletonLine className="text-[0.8125rem]" width="w-28" />
                </div>
                <div className="mt-1">
                  <div className="h-5" />
                  <Skeleton className="aspect-[340/210] @md:aspect-[520/210]" />
                </div>
              </div>
            </PanelFrame>
          ))}
        </div>

        <div className="rounded-lg border border-border bg-card">
          <div className="flex min-h-10 items-center rounded-t-[3px] border-b border-border bg-panel-head px-3.5 py-1.5">
            <h2 className="text-[0.8125rem] font-semibold">{t("priorities")}</h2>
          </div>
          <div className="px-3.5 py-3">
            <FollowUpSkeleton rows={1} />
          </div>
        </div>
      </Loading>
    </>
  );
}
