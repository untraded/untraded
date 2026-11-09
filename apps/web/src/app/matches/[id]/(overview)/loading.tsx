// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import {
  PrioritiesSkeleton,
  RatingSkeleton,
  RoundsSkeleton,
  SidesSkeleton,
  TeamSkeleton,
} from "@/components/match/match-skeletons";
import { Loading, Skeleton, SkeletonLine, slots } from "@/components/skeleton";
import { ContextBar } from "@/components/ui/context-bar";

/** The match page while it loads: the context bar's place, the back link, the rounds, then the
 * player's panels beside both teams, laid out as the page (a ready match the player played, the
 * common case). Same columns and paddings as the page and `MatchContext`. */
export default async function MatchLoading() {
  const t = await getTranslations("match");
  return (
    <>
      {/* The context bar's place, so that the page does not jump when it arrives. */}
      <ContextBar label={t("context.label")}>
        <div className="flex items-baseline gap-x-3 xl:shrink-0">
          <SkeletonLine className="text-lg leading-tight" width="w-24" />
          <SkeletonLine className="text-lg leading-tight" width="w-12" />
          <Skeleton className="h-6 w-20 self-center rounded-sm" />
        </div>
        <SkeletonLine className="text-[0.8125rem] xl:shrink-0" width="w-52" />
        <div className="flex gap-6 lg:ml-auto">
          {slots(2).map((i) => (
            <Skeleton key={i} className="h-[2.125rem] w-24" />
          ))}
        </div>
      </ContextBar>
      <Loading className="flex flex-col gap-6">
        <div className="flex flex-wrap items-baseline gap-x-5 gap-y-2">
          <Link href="/matches" className="text-[0.8125rem] text-link underline underline-offset-3">
            {t("back")}
          </Link>
          <SkeletonLine className="text-[0.8125rem]" width="w-24" />
        </div>
        <RoundsSkeleton title={t("rounds")} />
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="flex min-w-0 flex-col gap-6">
            <PrioritiesSkeleton title={t("priorities")} />
            <RatingSkeleton title={t("rating.title")} />
            <SidesSkeleton title={t("bySide")} />
          </div>
          <div className="flex min-w-0 flex-col gap-3.5">
            <TeamSkeleton />
            <TeamSkeleton />
          </div>
        </div>
      </Loading>
    </>
  );
}
