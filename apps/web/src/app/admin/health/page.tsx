// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { getFormatter, getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { AdminHeader } from "@/components/admin/admin-header";
import { CheckChip } from "@/components/admin/check-state";
import { Panel } from "@/components/ui/panel";
import type { Locale } from "@/i18n/locale";
import {
  type CheckState,
  diskState,
  dumpState,
  jobsState,
  LATE_HOURS,
  offsiteState,
  overall,
  sourcesState,
} from "@/lib/admin-health";
import { adminOnlyMetadata } from "@/lib/admin-metadata";
import { getAdminHealth, getMe } from "@/lib/api";
import { cn } from "@/lib/cn";
import { bytes, dateTime, number, percent } from "@/lib/format";

export async function generateMetadata(): Promise<Metadata> {
  return adminOnlyMetadata(async () => (await getTranslations("admin"))("health"));
}

/**
 * How the server is doing: backups and their off-site copy, disk, jobs, collection and database.
 * Each check with a state says it in its band (a word and an icon of its own shape); the context
 * bar sums them up. A player who is not an admin gets the 404: the page does not say it exists.
 */
export default async function AdminHealth() {
  const me = await getMe();
  if (!me) redirect("/");
  if (!me.admin) notFound();
  const [health, t, format, locale, timeZone] = await Promise.all([
    getAdminHealth(),
    getTranslations("admin"),
    getFormatter(),
    getLocale() as Promise<Locale>,
    getTimeZone(),
  ]);
  if (!health) redirect("/");
  const now = Date.now();
  const { backups } = health;
  const dump = dumpState(backups, now);
  const offsite = offsiteState(backups.offsite, now);
  const disk = diskState(health.disk);
  const jobs = jobsState(health);
  const sources = sourcesState(health.sources);
  const summary = overall([dump, offsite.state, disk.state, jobs, sources]);
  const chip = (state: CheckState) => <CheckChip state={state} label={t(`checks.${state}`)} />;
  const ago = (at: string) => format.relativeTime(new Date(at), now);
  return (
    <>
      <AdminHeader current="health">
        <CheckChip
          state={summary.state}
          label={t(`overall.${summary.state}`, { count: summary.count })}
        />
      </AdminHeader>
      <div className="flex flex-col gap-4">
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title={t("backups")} aside={chip(dump)} bodyClassName="text-sm">
            {backups.last && dump !== "unknown" ? (
              <p>
                {t("lastDump", {
                  name: backups.last.name,
                  date: dateTime(backups.last.at, locale, timeZone),
                  size: bytes(backups.last.bytes, locale),
                })}{" "}
                <span className="text-muted-foreground">({ago(backups.last.at)})</span>
              </p>
            ) : backups.last ? (
              <p translate="no">{backups.last.name}</p>
            ) : (
              <p>{t("noDump")}</p>
            )}
            {dump === "warn" && <p className="mt-1">{t("dumpLate", { hours: LATE_HOURS })}</p>}
            <p className="mt-1 text-muted-foreground">
              {t("dumps", { daily: backups.daily, weekly: backups.weekly })}
            </p>
          </Panel>
          <Panel title={t("offsite")} aside={chip(offsite.state)} bodyClassName="text-sm">
            {backups.offsite ? (
              <>
                <p>
                  {offsite.at
                    ? t("offsiteRan", {
                        date: dateTime(offsite.at, locale, timeZone),
                        ago: ago(offsite.at),
                      })
                    : t("offsiteNoDate")}
                </p>
                {offsite.late && <p className="mt-1">{t("offsiteLate", { hours: LATE_HOURS })}</p>}
                {offsite.message && (
                  <p
                    className={cn(
                      "mt-1 font-mono text-[0.8125rem] break-words",
                      offsite.state === "fail" ? "text-destructive" : "text-muted-foreground",
                    )}
                    translate="no"
                  >
                    {offsite.message}
                  </p>
                )}
                <details className="mt-2 text-xs">
                  <summary className="w-fit cursor-pointer text-muted-foreground hover:text-foreground">
                    {t("offsiteRaw")}
                  </summary>
                  <pre className="mt-1.5 overflow-x-auto rounded-sm bg-muted p-2 font-mono">
                    {JSON.stringify(backups.offsite, null, 2)}
                  </pre>
                </details>
              </>
            ) : (
              <p className="text-muted-foreground">{t("noOffsite")}</p>
            )}
          </Panel>
          <Panel title={t("disk")} aside={chip(disk.state)} bodyClassName="text-sm">
            {health.disk && disk.used !== null ? (
              <>
                <p className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <span className="font-semibold tabular-nums">
                    {t("diskUsed", { used: percent(disk.used * 100, locale) })}
                  </span>
                  <span className="text-muted-foreground tabular-nums">
                    {t("diskLine", {
                      free: bytes(health.disk.free, locale),
                      total: bytes(health.disk.total, locale),
                    })}
                  </span>
                </p>
                <div aria-hidden="true" className="mt-2 h-2 overflow-hidden rounded-sm bg-muted">
                  <div
                    className={cn(
                      "h-full",
                      disk.state === "fail" ? "bg-destructive" : "bg-foreground/70",
                    )}
                    style={{ width: `${Math.round(disk.used * 100)}%` }}
                  />
                </div>
              </>
            ) : (
              <p className="text-muted-foreground">{t("noDisk")}</p>
            )}
          </Panel>
          <Panel title={t("sources")} aside={chip(sources)} bodyClassName="text-sm">
            <p className="tabular-nums">{t("sourcesLine", health.sources)}</p>
          </Panel>
        </div>
        <Panel
          title={t("failedJobs")}
          aside={
            <>
              {health.failed_jobs.length > 0 && (
                <span className="tabular-nums">
                  {t("failedCount", { count: health.failed_jobs.length })}
                </span>
              )}
              {chip(jobs)}
            </>
          }
          flush
        >
          {health.failed_jobs.length === 0 ? (
            <p className="px-3.5 py-3 text-sm text-muted-foreground">{t("noFailedJobs")}</p>
          ) : (
            <>
              <p className="border-b border-line-soft px-3.5 py-2 text-xs text-muted-foreground">
                {t("failedJobsLead")}
              </p>
              <ul>
                {health.failed_jobs.map((job) => (
                  <li
                    key={`${job.kind}-${job.at}`}
                    className="grid gap-x-4 gap-y-0.5 border-t border-line-soft px-3.5 py-2 first:border-t-0 sm:grid-cols-[6rem_minmax(0,1fr)_auto]"
                  >
                    <span className="font-mono text-[0.8125rem] font-semibold" translate="no">
                      {job.kind}
                    </span>
                    <span className="text-[0.8125rem] break-words">{job.error}</span>
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {t("attempts", { count: job.attempts })}, {dateTime(job.at, locale, timeZone)}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Panel>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Panel title={t("jobs")}>
            <Counts values={health.jobs} locale={locale} />
          </Panel>
          <Panel title={t("matches7")}>
            <Counts values={health.matches_7_days} locale={locale} />
          </Panel>
          <Panel title={t("database")}>
            <p className="text-xl font-semibold tabular-nums">
              {bytes(health.database_bytes, locale)}
            </p>
          </Panel>
        </div>
      </div>
    </>
  );
}

/** Counts by status, as the API names them (`queued`, `ready`…). */
function Counts({ values, locale }: { values: Record<string, number>; locale: Locale }) {
  const entries = Object.entries(values);
  if (entries.length === 0) return <p className="text-sm text-muted-foreground">0</p>;
  return (
    <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 text-sm">
      {entries.map(([status, count]) => (
        <div key={status} className="contents">
          <dt className="font-mono text-[0.8125rem] text-muted-foreground" translate="no">
            {status}
          </dt>
          <dd className="text-right font-semibold tabular-nums">{number(count, locale)}</dd>
        </div>
      ))}
    </dl>
  );
}
