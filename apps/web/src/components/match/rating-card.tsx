// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { Panel } from "@/components/ui/panel";
import type { Locale } from "@/i18n/locale";
import type { RatingDetail } from "@/lib/api";
import { cn } from "@/lib/cn";
import { number } from "@/lib/format";

/** The order the parts read in: what was done, what it cost, then the scale's own parts. */
const ORDER = [
  "shooting",
  "utility",
  "trade",
  "objective",
  "taken",
  "team",
  "balance",
  "baseline",
] as const;

/**
 * The player's Untraded Rating (beta) in this match: the match rating and its margin, the level
 * (what the player is worth, on the same scale), then the parts the match rating adds up from,
 * each a signed bar. Links to its formula.
 */
export async function RatingCard({
  rating,
  locale,
}: {
  rating: RatingDetail | null;
  locale: Locale;
}) {
  const t = await getTranslations("match.rating");
  const m = await getTranslations("matches");
  const parts = ORDER.flatMap((part) => rating?.parts.filter((p) => p.part === part) ?? []);
  const widest = Math.max(0.01, ...parts.map((p) => Math.abs(p.points)));
  const signed = (value: number) => {
    const shown = Math.round(value * 100) / 100;
    return `${shown > 0 ? "+" : shown < 0 ? "−" : ""}${number(Math.abs(shown), locale, 2)}`;
  };
  return (
    // The context bar's rating links here (`#match-rating`).
    <div id="match-rating">
      <Panel
        title={
          <>
            {t("title")}{" "}
            <span className="rounded-[3px] border border-border px-1 text-[0.6875rem] font-medium text-muted-foreground">
              {m("beta")}
            </span>
          </>
        }
        aside={
          <Link href="/formulas/rating.untraded" className="text-link underline underline-offset-3">
            {t("formula")}
          </Link>
        }
        bodyClassName="flex flex-col gap-3"
      >
        {rating?.value == null ? (
          <p className="text-sm text-muted-foreground">{t("none")}</p>
        ) : (
          <>
            <p className="flex flex-wrap items-baseline gap-x-2.5">
              <span className="text-3xl font-semibold tabular-nums">
                {number(rating.value, locale, 2)}
              </span>
              {rating.margin !== null && (
                <span className="text-sm text-muted-foreground tabular-nums">
                  {t("margin", { margin: number(rating.margin, locale, 2) })}
                </span>
              )}
              {rating.rounds !== null && (
                <span className="text-xs text-muted-foreground">
                  {t("rounds", { rounds: rating.rounds })}
                </span>
              )}
            </p>
            {rating.level != null && (
              <p className="text-sm text-muted-foreground">
                {t.rich("level", {
                  level: number(rating.level, locale, 2),
                  b: (chunks) => (
                    <span className="font-semibold text-foreground tabular-nums">{chunks}</span>
                  ),
                })}
              </p>
            )}
            {parts.length > 0 && (
              <ul className="flex flex-col gap-1.5">
                {parts.map((p) => (
                  <li
                    key={p.part}
                    className="grid grid-cols-[6.5rem_minmax(0,1fr)_3.5rem] sm:grid-cols-[9rem_minmax(0,1fr)_3.5rem] items-center gap-x-3 text-sm"
                  >
                    <span>{t(`parts.${p.part}`)}</span>
                    {/* A bar from the middle: right when the part adds, left when it costs. */}
                    <span
                      aria-hidden="true"
                      className="relative h-2.5 before:absolute before:inset-y-[-3px] before:left-1/2 before:w-px before:bg-border"
                    >
                      <span
                        className={cn(
                          "absolute top-0 h-full rounded-[2px]",
                          p.points >= 0 ? "left-1/2 bg-win" : "right-1/2 bg-loss",
                        )}
                        style={{ width: `${(Math.abs(p.points) / widest) * 50}%` }}
                      />
                    </span>
                    <span className="text-right font-semibold tabular-nums">
                      {signed(p.points)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-muted-foreground">{t("hint")}</p>
          </>
        )}
      </Panel>
    </div>
  );
}
