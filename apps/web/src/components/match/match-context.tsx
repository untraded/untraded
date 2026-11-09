// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import { ContextBar } from "@/components/ui/context-bar";
import type { Locale } from "@/i18n/locale";
import type { MatchDetail } from "@/lib/api";
import { cn } from "@/lib/cn";
import { dateTime, mapName, number } from "@/lib/format";

/**
 * A match's context bar, which also holds the page's title: the map, the score from the player's
 * side, the result (a dot and the word, never the colour alone) or, before the analysis ends, its
 * status; the mode and the date; then the player's match rating and level, the first a link to
 * its breakdown on the page.
 */
export async function MatchContext({
  match,
  rating,
  level,
  locale,
  timeZone,
}: {
  match: MatchDetail;
  /** The player's match rating, `null` when there is none (not played, not analysed, too old). */
  rating: number | null;
  level: number | null;
  locale: Locale;
  timeZone: string;
}) {
  const t = await getTranslations("match");
  const results = await getTranslations("result");
  const status = await getTranslations("status");
  const ready = match.status === "ready";
  const result = ready ? match.my_result : null;
  const hasScore = match.score_a !== null && match.score_b !== null;
  const [mine, theirs] =
    match.my_team === "B" ? [match.score_b, match.score_a] : [match.score_a, match.score_b];
  const mode = `modes.${match.mode}`;
  const when = match.played_at ? dateTime(match.played_at, locale, timeZone) : null;
  return (
    <ContextBar label={t("context.label")}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 xl:shrink-0">
        <h1 className="text-lg leading-tight font-semibold">{mapName(match.map)}</h1>
        {hasScore && (
          <p className="text-lg leading-tight font-semibold tabular-nums">
            <span className="sr-only">{t("context.score")} </span>
            {mine}
            <span aria-hidden="true" className="px-0.5 text-muted-foreground">
              :
            </span>
            <span className="sr-only"> {t("context.to")} </span>
            {theirs}
          </p>
        )}
        <p className="inline-flex h-6 items-center gap-1.5 self-center rounded-sm bg-muted px-2 text-xs font-medium">
          {result ? (
            <span
              aria-hidden="true"
              className={cn(
                "size-2 rounded-full",
                result === "win" && "bg-win",
                result === "loss" && "bg-loss",
                result === "tie" && "bg-muted-foreground",
              )}
            />
          ) : (
            !ready && (
              <span
                aria-hidden="true"
                className={cn(
                  "size-2 rounded-full border border-muted-foreground",
                  (match.status === "parsing" || match.status === "downloading") &&
                    "bg-muted-foreground motion-safe:animate-pulse",
                )}
              />
            )
          )}
          {result ? results(result) : status(match.status)}
        </p>
      </div>
      <p className="flex flex-wrap gap-x-3 gap-y-0.5 text-[0.8125rem] text-muted-foreground xl:shrink-0">
        {t.has(mode) && <span>{t(mode)}</span>}
        {when && <span>{when}</span>}
      </p>
      {(rating !== null || level !== null) && (
        <dl className="flex flex-wrap gap-x-6 gap-y-1 lg:ml-auto xl:shrink-0 xl:flex-nowrap">
          {rating !== null && (
            <div className="grid leading-tight">
              <dt translate="no" className="text-[0.6875rem] text-muted-foreground">
                {t("context.urating")}
              </dt>
              <dd>
                <a
                  href="#match-rating"
                  className="text-[0.9375rem] font-semibold tabular-nums underline decoration-muted-foreground underline-offset-3 hover:decoration-foreground"
                >
                  <span className="sr-only">{t("context.toBreakdown")} </span>
                  {number(rating, locale, 2)}
                </a>
              </dd>
            </div>
          )}
          {level !== null && (
            <div className="grid leading-tight">
              <dt className="text-[0.6875rem] text-muted-foreground">{t("context.level")}</dt>
              <dd className="text-[0.9375rem] font-semibold tabular-nums">
                {number(level, locale, 2)}
              </dd>
            </div>
          )}
        </dl>
      )}
    </ContextBar>
  );
}
