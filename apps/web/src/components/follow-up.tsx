// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import { Sparkline } from "@/components/sparkline";
import type { Locale } from "@/i18n/locale";
import type { FollowUp } from "@/lib/api";
import { metric, type Trend, trend, trendClass } from "@/lib/format";

const ARROW: Record<Trend, string> = { better: "▲", worse: "▼", same: "=" };

/** Has the indicator of a previous priority moved the right way since that session? */
export function followTrend(item: FollowUp): Trend {
  return trend({
    metric_id: item.indicator,
    version: "",
    name: item.name,
    unit: item.unit,
    better: item.better,
    basis: item.basis,
    session: item.now,
    reference: item.then,
    delta: item.now === null || item.then === null ? null : item.now - item.then,
    cases: null,
    signed: false,
  });
}

/**
 * The previous priorities, over the last sessions: their name and direction, a line, then before
 * → now and the reference. `compact` puts each one on a single row (the phone home page).
 */
export async function FollowUpList({
  items,
  locale,
  compact = false,
}: {
  items: FollowUp[];
  locale: Locale;
  compact?: boolean;
}) {
  const t = await getTranslations("advice");
  const words = await getTranslations("sessions");
  return (
    <ul className="flex flex-col">
      {items.map((item) => {
        const format = (value: number | null) => metric(value, item.unit, item.basis, locale);
        const moved = followTrend(item);
        const direction =
          item.now === null ? null : (
            <span className={`${trendClass(moved)} text-[0.8125rem] whitespace-nowrap`}>
              <span aria-hidden="true">{ARROW[moved]}</span>{" "}
              {words(moved === "same" ? "stable" : moved)}
            </span>
          );
        const values = (
          <>
            {format(item.then)} →{" "}
            <span className="font-semibold text-foreground">
              {item.now === null ? t("followMissing") : format(item.now)}
            </span>
          </>
        );
        const history = item.history.map((point) => point.value);
        if (compact) {
          return (
            <li
              key={item.rule_id}
              className="grid grid-cols-[minmax(0,1fr)_3.5rem_auto] items-center gap-2.5 border-t border-line-soft py-2 first:border-t-0 first:pt-0"
            >
              <span className="text-sm">
                {t(`rules.${item.rule_id}.label`)}
                <span className="block text-xs text-muted-foreground">
                  {values}
                  {item.reference !== null &&
                    `, ${t("followReference", { reference: format(item.reference) })}`}
                </span>
              </span>
              <Sparkline values={history} trend={moved} />
              {direction}
            </li>
          );
        }
        return (
          <li
            key={item.rule_id}
            className="flex flex-col gap-1 border-t border-line-soft py-2.5 first:border-t-0 first:pt-0"
          >
            <div className="flex justify-between gap-2 text-sm">
              <span>{t(`rules.${item.rule_id}.label`)}</span>
              {direction}
            </div>
            <Sparkline values={history} trend={moved} className="h-8" />
            <div className="flex justify-between gap-2 text-xs text-muted-foreground">
              <span>{values}</span>
              {item.reference !== null && (
                <span>{t("followReference", { reference: format(item.reference) })}</span>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
