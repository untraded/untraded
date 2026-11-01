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
import { Loading, Skeleton, SkeletonLine } from "@/components/skeleton";

/** The match page while it loads: the header, the rounds, then the player's parts beside both
 * teams, laid out as the page (a ready match the player played, the common case). */
export default async function MatchLoading() {
  const t = await getTranslations("match");
  return (
    <Loading className="flex flex-col gap-7">
      <div className="flex flex-col gap-3">
        <Link
          href="/matches"
          className="self-start text-[0.8125rem] text-link underline underline-offset-3"
        >
          {t("back")}
        </Link>
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <SkeletonLine className="text-2xl" width="w-28" />
          <SkeletonLine className="text-[1.75rem] leading-none" width="w-16" />
          <Skeleton className="h-5 w-16 self-center" />
          <SkeletonLine className="text-[0.8125rem]" width="w-56" />
        </div>
      </div>
      <RoundsSkeleton />
      <div className="grid items-start gap-7 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex min-w-0 flex-col gap-7">
          <PrioritiesSkeleton />
          <RatingSkeleton />
          <SidesSkeleton />
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          <TeamSkeleton />
          <TeamSkeleton />
        </div>
      </div>
    </Loading>
  );
}
