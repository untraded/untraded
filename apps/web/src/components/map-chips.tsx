// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import type { getTranslations } from "next-intl/server";
import type { PlayedMap } from "@/lib/api";
import { cn } from "@/lib/cn";
import { mapName } from "@/lib/format";

/**
 * The maps of a session as chips on a single line, cut at the last chip that fits and ended by a
 * "+n" chip for the maps left out, in CSS only. Hidden from assistive technologies: the caller
 * lists the maps beside it.
 *
 * The chips wrap in a box one line high that hides the lines below. Every chip but the last
 * reserves at its end the room of a "+n" chip (`pr-11`) and holds that chip, counting the maps
 * after it; every chip but the first starts back over that room (`-ml-11`), opaque, so it covers
 * the "+n" of the chip before. A chip goes to the hidden line unless it fits with the room of its
 * own "+n": the last chip on the visible line always has room for its "+n", which shows only
 * there, with the exact count of the chips that wrapped. Never a chip cut in the middle, no
 * measure, no breakpoint. The box takes the rest of the line, down to the first chip with its
 * "+n" (`flex-1 min-w-min`): narrower still (a small phone, a large font), the chips go under the
 * record, whole.
 *
 * With `matchHref`, each chip links to its match and the "+n" to `moreHref`, for the mouse only
 * (`tabIndex={-1}`): a chip on the hidden line must not take the keyboard's focus, so the caller
 * gives the keyboard its own links.
 */
export function MapChips({
  maps,
  t,
  matchHref,
  moreHref,
}: {
  maps: PlayedMap[];
  t: Awaited<ReturnType<typeof getTranslations<"sessions">>>;
  matchHref?: (matchId: string) => string;
  moreHref?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className="flex h-5 min-w-min flex-1 flex-wrap gap-x-2.5 overflow-hidden leading-5"
    >
      {maps.map((played, i) => {
        const after = maps.length - 1 - i;
        const content = (
          <>
            {played.result && (
              <span
                className={cn(
                  "rounded-sm px-1 text-[0.6875rem] leading-4 font-semibold",
                  played.result === "win" && "bg-win/15",
                  played.result === "loss" && "bg-loss/15",
                  played.result === "tie" && "bg-muted",
                )}
              >
                {t(`resultShort.${played.result}`)}
              </span>
            )}
            <span
              translate="no"
              className={cn("whitespace-nowrap", matchHref && "group-hover/chip:underline")}
            >
              {mapName(played.map)}
            </span>
            {played.my_score !== null && played.their_score !== null && (
              <span className="whitespace-nowrap text-muted-foreground tabular-nums">
                {played.my_score}–{played.their_score}
              </span>
            )}
          </>
        );
        const more = (
          <span className="inline-block rounded-sm px-1 text-[0.6875rem] leading-4 font-semibold text-muted-foreground ring-1 ring-border ring-inset group-hover/more:text-foreground">
            {t("more", { count: after })}
          </span>
        );
        return (
          <span
            key={played.match_id}
            className={cn(
              "relative inline-flex items-baseline gap-1.5 bg-card group-hover:bg-muted",
              after > 0 && "pr-11",
              i > 0 && "-ml-11",
            )}
          >
            {matchHref ? (
              <Link
                href={matchHref(played.match_id)}
                tabIndex={-1}
                className="group/chip inline-flex items-baseline gap-1.5"
              >
                {content}
              </Link>
            ) : (
              content
            )}
            {after > 0 && (
              // The room `pr-11` keeps, less the gap: the next chip, when on this line, covers it.
              <span
                title={t("moreMatches", { count: after })}
                className="absolute top-0 right-0 w-[2.125rem] pl-0.5"
              >
                {moreHref ? (
                  <a href={moreHref} tabIndex={-1} className="group/more">
                    {more}
                  </a>
                ) : (
                  more
                )}
              </span>
            )}
          </span>
        );
      })}
    </span>
  );
}
