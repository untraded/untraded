// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import type { Locale } from "@/i18n/locale";
import type { RatingDetail } from "@/lib/api";
import { cn } from "@/lib/cn";
import { number } from "@/lib/format";

/** The order the parts read in: what was done, then the baseline that sets the scale. */
const ORDER = ["kills", "deaths", "plants", "defuses", "baseline"] as const;

/**
 * The player's Untraded Rating (beta) in this match: its value and margin, then the parts it adds
 * up from, each a signed bar (kills earn, deaths cost, the baseline brings 1.00 to the average
 * player). Links to its formula.
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
  const signed = (value: number) =>
    `${value > 0 ? "+" : value < 0 ? "−" : ""}${number(Math.abs(value), locale, 2)}`;
  return (
    <section aria-labelledby="match-rating" className="flex flex-col gap-2">
      <h2
        id="match-rating"
        className="flex flex-wrap items-baseline justify-between gap-x-3 text-[0.8125rem] font-medium text-muted-foreground"
      >
        <span>
          {t("title")}{" "}
          <span className="rounded-[3px] border border-border px-1 text-[0.6875rem]">
            {m("beta")}
          </span>
        </span>
        <Link href="/formulas/rating.untraded" className="text-link underline underline-offset-3">
          {t("formula")}
        </Link>
      </h2>
      {rating?.value == null ? (
        <p className="rounded-md border border-border bg-card p-4 text-sm text-muted-foreground">
          {t("none")}
        </p>
      ) : (
        <div className="flex flex-col gap-3 rounded-md border border-border bg-card px-4 py-3.5">
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
          {parts.length > 0 && (
            <ul className="flex flex-col gap-1.5">
              {parts.map((p) => (
                <li
                  key={p.part}
                  className="grid grid-cols-[6.5rem_minmax(0,1fr)_3.5rem] items-center gap-x-3 text-sm"
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
                  <span className="text-right font-semibold tabular-nums">{signed(p.points)}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-muted-foreground">{t("hint")}</p>
        </div>
      )}
    </section>
  );
}
