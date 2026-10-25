// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import type { Locale } from "@/i18n/locale";
import type { MetricValue } from "@/lib/api";
import { number, percent } from "@/lib/format";
import { bySide, type Side } from "@/lib/match";

/**
 * The player's numbers on each side of the match, side by side. Values only: the two sides have
 * different round counts, and the session report is where numbers meet a reference.
 */
export async function SideSplit({
  metrics,
  rounds,
  locale,
}: {
  /** `null` when the API could not give the player's metrics. */
  metrics: MetricValue[] | null;
  rounds: Record<Side, number>;
  locale: Locale;
}) {
  const t = await getTranslations("match");
  const m = await getTranslations("matches");
  const s = await getTranslations("sessions");
  const has = metrics?.some((v) => v.scope === "ct" || v.scope === "t");
  const values = metrics ?? [];
  const pair = (id: string) => bySide(values, id);
  const rows: { name: string; ct: string; t: string }[] = [];
  const kills = pair("base.kills");
  const deaths = pair("base.deaths");
  const kd = (k: number | null | undefined, d: number | null | undefined) =>
    `${number(k, locale)}–${number(d, locale)}`;
  rows.push({ name: t("kd"), ct: kd(kills.ct, deaths.ct), t: kd(kills.t, deaths.t) });
  const adr = pair("base.adr");
  rows.push({ name: m("adr"), ct: number(adr.ct, locale), t: number(adr.t, locale) });
  const kast = pair("base.kast");
  rows.push({ name: m("kast"), ct: percent(kast.ct, locale), t: percent(kast.t, locale) });
  const untraded = pair("trade.untraded_deaths");
  rows.push({
    name: m("untraded"),
    ct: number(untraded.ct, locale),
    t: number(untraded.t, locale),
  });
  const won = pair("duel.opening_kills");
  const tried = pair("duel.opening_attempts");
  const of = (w: number | null | undefined, n: number | null | undefined) =>
    t("ofTried", { won: number(w, locale), tried: number(n, locale) });
  rows.push({ name: t("openings"), ct: of(won.ct, tried.ct), t: of(won.t, tried.t) });
  const rating = pair("rating.hltv1");
  rows.push({
    name: m("rating"),
    ct: number(rating.ct, locale, 2),
    t: number(rating.t, locale, 2),
  });

  return (
    <section aria-labelledby="match-sides" className="flex flex-col gap-2">
      <h2 id="match-sides" className="text-[0.8125rem] font-medium text-muted-foreground">
        {t("bySide")}
      </h2>
      {has ? (
        <table className="w-full overflow-hidden rounded-md border border-border bg-card text-sm tabular-nums">
          <thead>
            <tr className="text-xs text-muted-foreground">
              <th scope="col" className="px-4 py-2 text-left font-medium">
                <span className="sr-only">{s("metric")}</span>
              </th>
              <th scope="col" className="w-24 px-3 py-2 text-right font-semibold">
                <span className="text-side-ct">CT</span>
                <span className="block font-normal">{t("sideRounds", { rounds: rounds.CT })}</span>
              </th>
              <th scope="col" className="w-24 px-4 py-2 text-right font-semibold">
                <span className="text-side-t">T</span>
                <span className="block font-normal">{t("sideRounds", { rounds: rounds.T })}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.name} className="border-t border-line-soft">
                <th scope="row" className="px-4 py-2 text-left font-normal">
                  {row.name}
                </th>
                <td className="px-3 py-2 text-right">{row.ct}</td>
                <td className="px-4 py-2 text-right">{row.t}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="rounded-md border border-border bg-card p-4 text-sm text-muted-foreground">
          {t("sideMissing")}
        </p>
      )}
    </section>
  );
}
