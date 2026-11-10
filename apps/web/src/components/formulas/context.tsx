// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { Loading, Skeleton } from "@/components/skeleton";
import { ContextBar } from "@/components/ui/context-bar";
import type { Locale } from "@/i18n/locale";
import { apiGetOptional, type SessionList, type SessionReport } from "@/lib/api";
import { cn } from "@/lib/cn";
import { compare, gapPercent, gapTrend, metric, trendClass } from "@/lib/format";

const ARROW = { better: "▲", worse: "▼", same: "=" } as const;

/**
 * A formula's context bar, which also holds the page's title: the metric's name and id, then its
 * family, version, unit and which way is better, and at the right the player's value on their last
 * session (`children`, streamed in).
 */
export async function FormulaContext({
  name,
  id,
  family,
  version,
  unit,
  better,
  label,
  children,
}: {
  name: string;
  id: string;
  family: string;
  version: string;
  unit: string;
  better: ReactNode;
  label: string;
  children: ReactNode;
}) {
  const t = await getTranslations("formulas.context");
  const facts = [
    { key: "family", value: family },
    { key: "version", value: <span className="tabular-nums">{version}</span> },
    { key: "unit", value: unit },
    { key: "better", value: better },
  ];
  return (
    <ContextBar label={label}>
      <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-0.5">
        <h1 className="text-lg leading-tight font-semibold text-balance">{name}</h1>
        <code translate="no" className="font-mono text-xs break-all text-muted-foreground">
          {id}
        </code>
      </div>
      <dl className="flex flex-wrap gap-x-5 gap-y-1.5 xl:shrink-0 xl:flex-nowrap">
        {facts.map((fact) => (
          <div key={fact.key} className="grid leading-tight">
            <dt className="text-[0.6875rem] text-muted-foreground">{t(fact.key)}</dt>
            <dd className="text-[0.8125rem] font-medium whitespace-nowrap">{fact.value}</dd>
          </div>
        ))}
      </dl>
      {children}
    </ContextBar>
  );
}

/** The place of the player's value while it loads: as tall as the value, never announced. */
export function YourSessionSkeleton() {
  return (
    <Loading announce={false}>
      <div className="grid gap-1 lg:ml-auto xl:shrink-0">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-4.5 w-32" />
      </div>
    </Loading>
  );
}

/**
 * The player's value on their last session, an extra the page stands without: streamed, so the
 * formula does not wait on the session's report. The value opens the report; the gap to the
 * reference (arrow and sign, never the colour alone) follows when the metric is ranked.
 */
export async function YourSession({ id, locale }: { id: string; locale: Locale }) {
  const latest = (await apiGetOptional<SessionList>("/sessions?limit=1&offset=0"))?.items[0];
  const report = latest
    ? await apiGetOptional<SessionReport>(`/sessions/${encodeURIComponent(latest.id)}`)
    : null;
  const mine = report?.metrics.find((c) => c.metric_id === id);
  if (!mine || !report) return null;
  const [t, s] = await Promise.all([getTranslations("formulas"), getTranslations("sessions")]);
  const compared = compare(mine, report.rounds);
  const moved = compared.kind === "ranked" ? gapTrend(compared.gap) : null;
  return (
    <dl className="grid leading-tight lg:ml-auto xl:shrink-0">
      <dt className="text-[0.6875rem] text-muted-foreground">{t("yourSession")}</dt>
      <dd className="flex flex-wrap items-baseline gap-x-2 tabular-nums">
        <Link
          href={`/sessions/${encodeURIComponent(report.id)}`}
          className="text-[0.9375rem] font-semibold underline decoration-muted-foreground underline-offset-3 hover:decoration-foreground"
        >
          <span className="sr-only">{t("openReport")}, </span>
          {metric(mine.session, mine.unit, mine.basis, locale)}
        </Link>
        {moved && (
          <span className={cn("text-xs whitespace-nowrap", trendClass(moved))}>
            <span aria-hidden="true">{ARROW[moved]}</span> {gapPercent(compared.gap, locale)}
          </span>
        )}
        <span className="text-xs whitespace-nowrap text-muted-foreground">
          {s("vsReference", { value: metric(mine.reference, mine.unit, mine.basis, locale) })}
        </span>
      </dd>
    </dl>
  );
}
