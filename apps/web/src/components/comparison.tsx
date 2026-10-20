// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Locale } from "@/i18n/locale";
import type { Comparison } from "@/lib/api";
import { delta, metric, trend, trendClass } from "@/lib/format";

/** One metric: the session's value, and how far it is from the player's own 30 days. */
export function ComparisonCard({
  comparison,
  locale,
  perRound,
}: {
  comparison: Comparison;
  locale: Locale;
  perRound: string;
}) {
  const { unit, basis } = comparison;
  return (
    <div className="rounded border border-border px-4 py-3">
      <p className="text-xs text-muted-foreground">
        {comparison.name}
        {basis === "per_round" && <span className="text-muted-foreground"> · {perRound}</span>}
      </p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">
        {metric(comparison.session, unit, basis, locale)}
      </p>
      {comparison.reference !== null && (
        <p className="text-xs text-muted-foreground tabular-nums">
          <span className={trendClass(trend(comparison))}>
            {delta(comparison.delta, unit, basis, locale)}
          </span>{" "}
          · {metric(comparison.reference, unit, basis, locale)}
        </p>
      )}
    </div>
  );
}
