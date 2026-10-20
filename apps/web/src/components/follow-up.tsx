// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import type { Locale } from "@/i18n/locale";
import type { FollowUp } from "@/lib/api";
import { metric, trend, trendClass } from "@/lib/format";

/** The previous session's priorities: has their indicator moved the right way since? */
export async function FollowUps({ items, locale }: { items: FollowUp[]; locale: Locale }) {
  if (items.length === 0) return null;
  const t = await getTranslations("advice");
  return (
    <section className="mt-6">
      <h2 className="mb-2 text-sm font-medium text-zinc-400">{t("followTitle")}</h2>
      <ul className="divide-y divide-zinc-800 rounded border border-zinc-800 text-sm">
        {items.map((item) => {
          const format = (value: number | null) => metric(value, item.unit, item.basis, locale);
          const moved = trend({
            metric_id: item.indicator,
            version: "",
            name: item.name,
            unit: item.unit,
            better: item.better,
            basis: item.basis,
            session: item.now,
            reference: item.then,
            delta: item.now === null || item.then === null ? null : item.now - item.then,
          });
          return (
            <li
              key={item.rule_id}
              className="flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2"
            >
              <span className="flex-1">
                {t("followLine", {
                  name: t(`rules.${item.rule_id}.label`),
                  before: format(item.then),
                  now: item.now === null ? t("followMissing") : format(item.now),
                })}
              </span>
              {item.reference !== null && (
                <span className="text-xs text-zinc-500">
                  {t("followReference", { reference: format(item.reference) })}
                </span>
              )}
              <Sparkline values={item.history.map((p) => p.value)} tone={trendClass(moved)} />
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** The indicator over the last sessions: a line, the last point marked. */
function Sparkline({ values, tone }: { values: (number | null)[]; tone: string }) {
  const known = values.flatMap((v, i) => (v === null ? [] : [{ i, v }]));
  if (known.length < 2) return null;
  const width = 80;
  const height = 24;
  const low = Math.min(...known.map((p) => p.v));
  const high = Math.max(...known.map((p) => p.v));
  const x = (i: number) => (i / Math.max(1, values.length - 1)) * (width - 4) + 2;
  const y = (v: number) =>
    high === low ? height / 2 : height - 2 - ((v - low) / (high - low)) * (height - 4);
  const points = known.map((p) => `${x(p.i)},${y(p.v)}`).join(" ");
  const last = known.at(-1);
  return (
    <svg width={width} height={height} className={tone} aria-hidden="true">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" />
      {last && <circle cx={x(last.i)} cy={y(last.v)} r="2.5" fill="currentColor" />}
    </svg>
  );
}
