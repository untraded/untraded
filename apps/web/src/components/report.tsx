// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { Info, Scale } from "lucide-react";
import { cookies } from "next/headers";
import Link from "next/link";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { FollowUpList } from "@/components/follow-up";
import { type GapRow, MetricGaps } from "@/components/metric-gaps";
import { Priorities } from "@/components/priorities";
import { describeReference } from "@/components/reference";
import { ResultBadge } from "@/components/result-badge";
import { type Locale, pickTone, TONE_COOKIE } from "@/i18n/locale";
import { findMatch, type MatchDetail, type SessionReport } from "@/lib/api";
import {
  compare,
  dateRange,
  delta,
  FEW_CASES,
  family,
  gap,
  gapPercent,
  gapTrend,
  killDiff,
  MIN_CASES,
  mapName,
  metric,
  number,
  score,
  shortDay,
  type Trend,
  trend,
  trendClass,
} from "@/lib/format";
import { catalogFor } from "@/lib/metric-docs-files";

const FAMILIES = ["base", "rating", "duel", "trade", "clutch", "util", "eco", "pos"];
const STANDOUT = 5;
const ARROW: Record<Trend, string> = { better: "▲", worse: "▼", same: "=" };

/**
 * A session report: the priorities first with the context beside them (key figures against the
 * reference, follow-up of the previous priorities, matches), then every metric as its gap to the
 * reference. `back` adds the link to the session list.
 */
export async function Report({
  report,
  back,
  readOnly = false,
}: {
  report: SessionReport;
  back: boolean;
  /** The read-only demo: the priorities take no vote. */
  readOnly?: boolean;
}) {
  const t = await getTranslations("sessions");
  const families = await getTranslations("families");
  const formulas = await getTranslations("formulas");
  const advice = await getTranslations("advice");
  const columns = await getTranslations("matches");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const tone = pickTone((await cookies()).get(TONE_COOKIE)?.value);
  const { reference } = report;
  const named = await describeReference(reference, locale);

  // The matches the evidence comes from, to draw their rounds. One that fails to load leaves its
  // evidence as a plain list of rounds rather than breaking the report.
  const ids = [...new Set(report.advice.flatMap((a) => a.evidence.map((e) => e.match_id)))];
  const matches = new Map<string, MatchDetail>();
  for (const match of await Promise.all(ids.map((id) => findMatch(id)))) {
    if (match) matches.set(match.id, match);
  }

  // Metric names in the player's language, from the formulas' catalog; the API gives English.
  const names = catalogFor(locale)?.names ?? {};
  const rows: GapRow[] = report.metrics.map((c) => {
    const { kind, gap: value } = compare(c, report.rounds);
    const name = names[c.metric_id] ?? c.name;
    const perRound = c.basis === "per_round" ? t("perRound") : null;
    return {
      id: c.metric_id,
      name,
      formula: formulas("open", { name }),
      family: families(family(c.metric_id)),
      perRound,
      value: metric(c.session, c.unit, c.basis, locale),
      reference: t("vsReference", { value: metric(c.reference, c.unit, c.basis, locale) }),
      gap: value,
      kind,
      // What a rate stands on, said when it is little: under the name if ranked, in place of the
      // gap if too few to rank.
      cases:
        c.cases !== null && c.cases < FEW_CASES && (kind === "ranked" || kind === "few")
          ? t("casesOf", { count: c.cases })
          : null,
      // A signed metric reads as its difference in units; every other one as a share.
      gapText:
        kind === "units"
          ? [delta(c.delta, c.unit, c.basis, locale), perRound].filter(Boolean).join(" ")
          : gapPercent(value, locale),
      trend: kind === "units" ? trend(c) : gapTrend(value),
    };
  });
  const byGap = (a: GapRow, b: GapRow) =>
    (a.gap ?? Number.POSITIVE_INFINITY) - (b.gap ?? Number.POSITIVE_INFINITY);
  const groups = FAMILIES.map((key) => ({
    key,
    label: families(key),
    rows: rows.filter((row) => family(row.id) === key).sort(byGap),
  })).filter((group) => group.rows.length > 0);
  const ranked = rows.filter((row) => row.kind === "ranked").sort(byGap);
  const standout = reference.enough
    ? {
        worse: ranked.filter((row) => row.trend === "worse").slice(0, STANDOUT),
        better: ranked
          .filter((row) => row.trend === "better")
          .reverse()
          .slice(0, STANDOUT),
      }
    : null;

  return (
    <article className="flex flex-col gap-7">
      <header className="flex flex-col gap-2.5">
        {back && (
          <Link href="/sessions" className="text-sm text-muted-foreground hover:text-foreground">
            ← {t("back")}
          </Link>
        )}
        <h1 className="text-2xl leading-tight font-semibold text-balance sm:text-[1.75rem]">
          {t("titleOf", { date: shortDay(report.started_at, locale, timeZone) })}
        </h1>
        <p className="flex flex-wrap gap-x-4 gap-y-1 text-[0.9375rem] text-muted-foreground">
          <span>{dateRange(report.started_at, report.ended_at, locale, timeZone)}</span>
          <span>{t("count", { matches: report.matches, rounds: report.rounds })}</span>
          <span className="font-semibold text-foreground">
            {t("recordLong", { wins: report.wins, losses: report.losses, ties: report.ties })}
          </span>
        </p>
        {named.short ? (
          <p className="flex max-w-[78ch] gap-2.5 text-sm text-muted-foreground">
            <Scale aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span>
              <span className="font-semibold text-foreground">
                {t("referenceLabel", { reference: named.short })}
              </span>{" "}
              {named.sentence}
            </span>
          </p>
        ) : (
          <div className="flex max-w-[78ch] gap-3 rounded-lg border border-border bg-card px-3.5 py-3 text-sm">
            <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
            <div>
              <p className="font-semibold">{t("noReferenceTitle")}</p>
              <p className="text-muted-foreground">{named.sentence}</p>
            </div>
          </div>
        )}
      </header>

      <div className="grid items-start gap-7 lg:grid-cols-[minmax(0,1fr)_18.75rem]">
        <Priorities
          advice={report.advice}
          sessionId={report.id}
          locale={locale}
          tone={tone}
          hasReference={reference.enough}
          matches={matches}
          readOnly={readOnly}
        />
        <aside className="flex flex-col gap-3.5">
          <Box title={t("keyFigures")}>
            <ul className="grid gap-x-4 sm:grid-cols-2 lg:grid-cols-1">
              {report.headlines.map((c) => {
                const moved = gapTrend(gap(c));
                return (
                  <li
                    key={c.metric_id}
                    className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-2.5 border-t border-line-soft py-2 first:border-t-0 first:pt-0 sm:[&:nth-child(2)]:border-t-0 sm:[&:nth-child(2)]:pt-0 lg:[&:nth-child(2)]:border-t lg:[&:nth-child(2)]:pt-2"
                  >
                    <span className="text-[0.8125rem] text-muted-foreground">
                      {names[c.metric_id] ?? c.name}
                      {c.basis === "per_round" && `, ${t("perRound")}`}
                    </span>
                    <span className="text-right text-xl leading-tight font-semibold">
                      {metric(c.session, c.unit, c.basis, locale)}
                    </span>
                    <span className="col-span-2 flex justify-between gap-2 text-xs">
                      {reference.enough && c.reference !== null ? (
                        <>
                          <span className={trendClass(moved)}>
                            <span aria-hidden="true">{ARROW[moved]}</span>{" "}
                            {delta(c.delta, c.unit, c.basis, locale)}
                          </span>
                          <span className="text-muted-foreground">
                            {t("vsReference", {
                              value: metric(c.reference, c.unit, c.basis, locale),
                            })}
                          </span>
                        </>
                      ) : (
                        <span className="text-muted-foreground">{t("noReference")}</span>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          </Box>
          {report.follow_up.length > 0 && (
            <Box title={advice("followTitle")}>
              <FollowUpList items={report.follow_up} locale={locale} />
            </Box>
          )}
          <Box title={t("sessionMatches")}>
            <ul>
              {report.match_list.map((match) => (
                <li key={match.id} className="border-t border-line-soft first:border-t-0">
                  <Link
                    href={`/matches/${match.id}`}
                    className="-mx-2 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-0.5 rounded-md px-2 py-2 text-sm hover:bg-muted"
                  >
                    <span className="flex items-center gap-2">
                      <span className="font-semibold">{mapName(match.map)}</span>
                      <span className="text-muted-foreground">
                        {score(match.score_a, match.score_b, match.my_team)}
                      </span>
                    </span>
                    <ResultBadge result={match.my_result} status={match.status} />
                    <span className="col-span-2 text-xs text-muted-foreground">
                      {columns("kd")} {killDiff(match.my_line)},{" "}
                      {columns(match.my_line?.untraded == null ? "rating" : "urating")}{" "}
                      {number(match.my_line?.untraded ?? match.my_line?.hltv1, locale, 2)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </Box>
        </aside>
      </div>

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-lg font-semibold">{t("allMetrics")}</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {named.short && reference.enough
              ? `${t("metricsLead", { count: rows.length, reference: named.short })} ${t("metricsRule", { min: MIN_CASES })}`
              : t("metricsLeadNone", { count: rows.length })}
          </p>
        </div>
        <MetricGaps
          families={groups}
          standout={standout}
          labels={{
            standout: t("standout"),
            worseThan: t("worseThan"),
            betterThan: t("betterThan"),
            families: t("families"),
            metric: t("metric"),
            session: t("session"),
            delta: t("delta"),
            worse: t("gapWorse"),
            better: t("gapBetter"),
            neutral: t("neutral"),
            noReference: t("noReference"),
            rare: t("rare"),
            standoutEmpty: t("standoutEmpty"),
          }}
        />
      </section>
    </article>
  );
}

function Box({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-border bg-card px-4 py-3.5">
      <h2 className="mb-2.5 text-sm font-semibold">{title}</h2>
      {children}
    </section>
  );
}
