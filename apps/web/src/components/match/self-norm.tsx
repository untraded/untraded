// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import { PositionRuler } from "@/components/position-ruler";
import { Panel } from "@/components/ui/panel";
import type { Locale } from "@/i18n/locale";
import type { MatchSummary } from "@/lib/api";
import { cn } from "@/lib/cn";
import { number, percent } from "@/lib/format";
import { MIN_SPREAD_MATCHES, zoneTrend } from "@/lib/position";
import { MIN_ROUNDS, type SelfMetric, type SelfRow, selfRows, signed } from "@/lib/self-norm";

/** Decimals of each figure, as the match page shows them elsewhere (ratings to the hundredth,
 * ADR and KAST whole, K–D whole and signed); its mean and the gap may need one more. */
const DIGITS: Record<SelfMetric, { value: number; mean: number }> = {
  untraded: { value: 2, mean: 2 },
  adr: { value: 0, mean: 0 },
  kast: { value: 0, mean: 0 },
  kd: { value: 0, mean: 1 },
  untraded_deaths: { value: 2, mean: 2 },
};

const WORD: Record<"better" | "worse" | "same", string> = {
  better: "text-win",
  worse: "text-loss",
  same: "text-foreground",
};

/**
 * The top of the match page, beside what to review: the match's five figures, each against the
 * same figure over the player's previous ready matches (at most 30). Each row gives the value,
 * the mean of the previous matches, the graduated ruler (band = their 10th to 90th percentile,
 * tick = their median, dot = this match; better always on the right), a word for the zone and
 * the gap to the mean. Below `MIN_SPREAD_MATCHES` previous values, no ruler and a line that says
 * why; `previous` is `null` when they could not be read.
 */
export async function SelfNorm({
  match,
  previous,
  locale,
}: {
  match: MatchSummary;
  previous: MatchSummary[] | null;
  locale: Locale;
}) {
  const t = await getTranslations("match.self");
  const count = previous?.length ?? 0;
  const rows = selfRows(match, previous ?? []);

  const format = (id: SelfMetric, value: number | null, digits: number) =>
    id === "kast"
      ? percent(value, locale)
      : id === "kd"
        ? signed(value, locale, digits)
        : number(value, locale, digits);
  const gapText = (row: SelfRow) => {
    const digits = DIGITS[row.id].mean;
    const text = signed(row.gap, locale, digits);
    if (row.id === "kast") return t("points", { gap: text });
    if (row.better !== "lower" || row.gap === null) return text;
    const rounded = Number(row.gap.toFixed(digits));
    return rounded < 0 ? t("fewer", { gap: text }) : rounded > 0 ? t("more", { gap: text }) : text;
  };

  // One line for the whole panel when the previous matches are the reason no row has a ruler.
  const why =
    previous === null
      ? t("unavailable")
      : count === 0
        ? t("none")
        : count < MIN_SPREAD_MATCHES
          ? t("needsMatches", { min: MIN_SPREAD_MATCHES, count })
          : null;
  const anyRuler = rows.some((row) => row.position);

  return (
    <Panel
      title={count === 0 ? t("titleNone") : count === 1 ? t("titleOne") : t("title", { count })}
      aside={
        anyRuler && (
          <span>
            {t("better")} <span aria-hidden="true">▸</span>
          </span>
        )
      }
      flush
    >
      <ul>
        {rows.map((row) => {
          const name = t(`metric.${row.id}`);
          const value = format(row.id, row.value, DIGITS[row.id].value);
          const mean = row.norm ? format(row.id, row.norm.mean, DIGITS[row.id].mean) : null;
          const tone = row.position ? zoneTrend(row.position.zone) : null;
          const zone = row.position ? t(`zone.${row.position.zone}`) : null;
          const gap = row.gap === null ? null : gapText(row);
          const note =
            row.missing === "noValue"
              ? t(row.id === "untraded" ? "noRating" : "noValue")
              : row.missing === "noHistory" && count > 0
                ? t("noHistory")
                : row.missing === "few" && count >= MIN_SPREAD_MATCHES
                  ? t("few", { min: MIN_SPREAD_MATCHES, count: row.norm?.count ?? 0 })
                  : row.missing === "flat"
                    ? t("flat")
                    : null;
          return (
            <li
              key={row.id}
              className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 border-t border-line-soft px-3.5 py-2 first:border-t-0 sm:grid-cols-[minmax(6.5rem,1fr)_4.5rem_minmax(8rem,2fr)_7.25rem]"
            >
              <span className="text-sm leading-tight font-medium">
                {name}
                {row.id === "untraded_deaths" && (
                  <span className="block text-xs font-normal text-muted-foreground">
                    {t("perRound")}
                  </span>
                )}
              </span>
              {/* With a ruler, its label says the value and the mean: read once. */}
              <span
                aria-hidden={row.position ? true : undefined}
                className="text-right leading-tight"
              >
                <span className="font-semibold tabular-nums">{value}</span>
                {mean !== null && (
                  <span className="block text-xs text-muted-foreground tabular-nums">
                    {t("mean", { value: mean })}
                  </span>
                )}
              </span>
              <div className="col-span-2 sm:col-span-1">
                {row.position && tone && zone ? (
                  <PositionRuler
                    position={row.position}
                    tone={tone}
                    label={t("label", {
                      name,
                      value,
                      mean: mean ?? "",
                      zone,
                      gap: gap ?? "",
                    })}
                  />
                ) : (
                  note && <p className="text-xs text-muted-foreground">{note}</p>
                )}
              </div>
              {(zone || gap) && (
                <p
                  // Read with the ruler's label: said once to a screen reader.
                  aria-hidden={zone ? true : undefined}
                  className="col-span-2 flex flex-wrap items-baseline gap-x-1.5 text-xs leading-tight sm:col-span-1 sm:block"
                >
                  {zone && tone && <span className={cn("font-semibold", WORD[tone])}>{zone}</span>}
                  {gap && (
                    <span className="text-muted-foreground tabular-nums sm:block">
                      {zone ? gap : t("gapOnly", { gap })}
                    </span>
                  )}
                </p>
              )}
            </li>
          );
        })}
      </ul>
      {(anyRuler || why) && (
        <div className="flex flex-col gap-1.5 border-t border-line-soft px-3.5 py-2 text-xs text-muted-foreground">
          {why && <p>{why}</p>}
          {anyRuler && (
            <>
              <ul className="flex flex-wrap gap-x-4 gap-y-1">
                <li className="flex items-center gap-1.5">
                  <span aria-hidden="true" className="size-2.5 rounded-full bg-foreground" />
                  {t("legendDot")}
                </li>
                <li className="flex items-center gap-1.5">
                  <span aria-hidden="true" className="h-3 w-0.5 bg-muted-foreground" />
                  {t("legendMedian")}
                </li>
                <li className="flex items-center gap-1.5">
                  <span aria-hidden="true" className="h-2 w-[18px] rounded-[2px] bg-band" />
                  {t("legendBand")}
                </li>
              </ul>
              <p>{t("legendNote", { count, rounds: MIN_ROUNDS })}</p>
            </>
          )}
        </div>
      )}
    </Panel>
  );
}
