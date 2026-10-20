// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { cookies } from "next/headers";
import Link from "next/link";
import { getLocale, getTranslations } from "next-intl/server";
import { ComparisonCard } from "@/components/comparison";
import { FollowUps } from "@/components/follow-up";
import { Priorities } from "@/components/priorities";
import { ResultBadge } from "@/components/result-badge";
import { type Locale, pickTone, TONE_COOKIE } from "@/i18n/locale";
import type { Comparison, SessionReport } from "@/lib/api";
import { cn } from "@/lib/cn";
import {
  dateRange,
  day,
  delta,
  family,
  killDiff,
  mapName,
  metric,
  number,
  score,
  trend,
  trendClass,
} from "@/lib/format";

const FAMILIES = ["rating", "base", "duel", "trade", "clutch", "util", "eco", "pos"];

/** A session report: the priorities first, then follow-up, key figures, matches and every metric.
 * `back` adds the link to the session list (not on the latest report, which is its own page). */
export async function Report({ report, back }: { report: SessionReport; back: boolean }) {
  const t = await getTranslations("sessions");
  const families = await getTranslations("families");
  const locale = (await getLocale()) as Locale;
  const tone = pickTone((await cookies()).get(TONE_COOKIE)?.value);
  const { reference } = report;
  const groups = FAMILIES.map((name) => ({
    name,
    metrics: report.metrics.filter((m) => family(m.metric_id) === name),
  })).filter((group) => group.metrics.length > 0);

  return (
    <article>
      {back && (
        <Link
          href="/sessions"
          className="mb-4 inline-block text-sm text-muted-foreground hover:text-foreground"
        >
          ← {t("back")}
        </Link>
      )}
      <header>
        <h1 className="text-2xl font-semibold">
          {dateRange(report.started_at, report.ended_at, locale)}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("count", { matches: report.matches, rounds: report.rounds })} ·{" "}
          {t("record", { wins: report.wins, losses: report.losses, ties: report.ties })}
        </p>
        <p className="mt-3 text-sm text-foreground">
          {reference.kind === "self"
            ? t("reference", {
                matches: reference.matches,
                rounds: reference.rounds,
                since: day(reference.since, locale),
                until: day(reference.until, locale),
              })
            : reference.kind === "level"
              ? t("levelReference", {
                  low: number(reference.level_low, locale),
                  high: number(reference.level_high, locale),
                  matches: reference.matches,
                })
              : t("notEnough", {
                  minMatches: reference.min_matches,
                  minRounds: reference.min_rounds,
                  matches: reference.matches,
                  rounds: reference.rounds,
                })}
        </p>
      </header>

      <Priorities advice={report.advice} sessionId={report.id} locale={locale} tone={tone} />
      <FollowUps items={report.follow_up} locale={locale} />

      <div className="mt-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {report.headlines.map((c) => (
          <ComparisonCard
            key={c.metric_id}
            comparison={c}
            locale={locale}
            perRound={t("perRound")}
          />
        ))}
      </div>

      <section className="mt-8">
        <h2 className="mb-2 text-sm font-medium text-muted-foreground">{t("matches")}</h2>
        <ul className="divide-y divide-border rounded border border-border text-sm">
          {report.match_list.map((match) => (
            <li key={match.id}>
              <Link
                href={`/matches/${match.id}`}
                className="flex items-center gap-4 px-3 py-2 hover:bg-card"
              >
                <span className="w-24">{mapName(match.map)}</span>
                <span className="w-20 tabular-nums">
                  {score(match.score_a, match.score_b, match.my_team)}
                </span>
                <ResultBadge result={match.my_result} status={match.status} />
                <span className="ml-auto tabular-nums text-muted-foreground">
                  {killDiff(match.my_line)} · {number(match.my_line?.hltv1, locale, 2)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-8">
        <h2 className="mb-2 text-sm font-medium text-muted-foreground">{t("allMetrics")}</h2>
        <div className="overflow-x-auto rounded border border-border">
          <table className="w-full text-sm">
            <thead className="bg-card text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">{t("metric")}</th>
                <th className="px-3 py-2 text-right font-medium">{t("session")}</th>
                {reference.enough && (
                  <>
                    <th className="px-3 py-2 text-right font-medium">
                      {t(reference.kind === "level" ? "yoursLevel" : "yours")}
                    </th>
                    <th className="px-3 py-2 text-right font-medium">{t("delta")}</th>
                  </>
                )}
              </tr>
            </thead>
            {groups.map((group) => (
              <tbody key={group.name}>
                <tr className="border-t border-border bg-card">
                  <th
                    colSpan={reference.enough ? 4 : 2}
                    className="px-3 py-1.5 text-left text-xs font-medium text-foreground"
                  >
                    {families(group.name)}
                  </th>
                </tr>
                {group.metrics.map((c) => (
                  <MetricRow
                    key={c.metric_id}
                    comparison={c}
                    locale={locale}
                    perRound={t("perRound")}
                    withReference={reference.enough}
                  />
                ))}
              </tbody>
            ))}
          </table>
        </div>
      </section>
    </article>
  );
}

function MetricRow({
  comparison: c,
  locale,
  perRound,
  withReference,
}: {
  comparison: Comparison;
  locale: Locale;
  perRound: string;
  withReference: boolean;
}) {
  return (
    <tr className="border-t border-border">
      <td className="px-3 py-1.5">
        {c.name}
        {c.basis === "per_round" && <span className="text-muted-foreground"> · {perRound}</span>}
      </td>
      <td className="px-3 py-1.5 text-right tabular-nums">
        {metric(c.session, c.unit, c.basis, locale)}
      </td>
      {withReference && (
        <>
          <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">
            {metric(c.reference, c.unit, c.basis, locale)}
          </td>
          <td className={cn("px-3 py-1.5 text-right tabular-nums", trendClass(trend(c)))}>
            {delta(c.delta, c.unit, c.basis, locale)}
          </td>
        </>
      )}
    </tr>
  );
}
