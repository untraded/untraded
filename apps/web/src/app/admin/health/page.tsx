// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { AdminHeader } from "@/components/admin/admin-header";
import type { Locale } from "@/i18n/locale";
import { getAdminHealth, getMe } from "@/lib/api";
import { bytes, dateTime, number } from "@/lib/format";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("admin"))("health") };
}

/** How the server is doing: database, jobs, collection, backups and disk. */
export default async function AdminHealth() {
  const me = await getMe();
  if (!me) redirect("/");
  const t = await getTranslations("admin");
  if (!me.admin) {
    return <p className="text-muted-foreground">{t("forbidden")}</p>;
  }
  const health = await getAdminHealth();
  if (!health) redirect("/");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const { backups, disk } = health;
  const used = disk ? Math.round(((disk.total - disk.free) / disk.total) * 100) : 0;
  return (
    <section className="flex flex-col gap-5">
      <AdminHeader current="health" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Card title={t("database")}>
          <p className="text-2xl font-semibold">{bytes(health.database_bytes, locale)}</p>
        </Card>
        <Card title={t("jobs")}>
          <Counts values={health.jobs} locale={locale} />
        </Card>
        <Card title={t("matches7")}>
          <Counts values={health.matches_7_days} locale={locale} />
        </Card>
        <Card title={t("sources")}>
          <p>{t("sourcesLine", health.sources)}</p>
        </Card>
        <Card title={t("backups")}>
          <p>
            {backups.last
              ? t("lastDump", {
                  name: backups.last.name,
                  date: dateTime(backups.last.at, locale, timeZone),
                  size: bytes(backups.last.bytes, locale),
                })
              : t("noDump")}
          </p>
          <p className="text-muted-foreground">
            {t("dumps", { daily: backups.daily, weekly: backups.weekly })}
          </p>
          <p className="mt-2 font-medium">{t("offsite")}</p>
          {backups.offsite ? (
            <pre className="mt-1 overflow-x-auto rounded-md bg-muted p-2 font-mono text-xs">
              {JSON.stringify(backups.offsite, null, 2)}
            </pre>
          ) : (
            <p className="text-muted-foreground">{t("noOffsite")}</p>
          )}
        </Card>
        <Card title={t("disk")}>
          {disk ? (
            <>
              <p>
                {t("diskLine", {
                  free: bytes(disk.free, locale),
                  total: bytes(disk.total, locale),
                })}
              </p>
              <div aria-hidden="true" className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full bg-foreground/70" style={{ width: `${used}%` }} />
              </div>
            </>
          ) : (
            <p className="text-muted-foreground">{t("noDisk")}</p>
          )}
        </Card>
      </div>
      <Card title={t("failedJobs")}>
        {health.failed_jobs.length === 0 ? (
          <p className="text-muted-foreground">{t("noFailedJobs")}</p>
        ) : (
          <ul className="flex flex-col">
            {health.failed_jobs.map((job) => (
              <li
                key={`${job.kind}-${job.at}`}
                className="grid gap-x-4 border-t border-line-soft py-2 first:border-t-0 sm:grid-cols-[6rem_minmax(0,1fr)_auto]"
              >
                <span className="font-mono text-[0.8125rem]" translate="no">
                  {job.kind}
                </span>
                <span className="text-[0.8125rem] break-words">{job.error}</span>
                <span className="text-xs text-muted-foreground">
                  {t("attempts", { count: job.attempts })}, {dateTime(job.at, locale, timeZone)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-border bg-card px-4 py-3.5 text-sm">
      <h2 className="mb-2 font-semibold">{title}</h2>
      {children}
    </section>
  );
}

/** Counts by status, as the API names them (`queued`, `ready`…). */
function Counts({ values, locale }: { values: Record<string, number>; locale: Locale }) {
  const entries = Object.entries(values);
  if (entries.length === 0) return <p className="text-muted-foreground">0</p>;
  return (
    <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1">
      {entries.map(([status, count]) => (
        <div key={status} className="contents">
          <dt className="font-mono text-[0.8125rem] text-muted-foreground" translate="no">
            {status}
          </dt>
          <dd className="text-right font-semibold">{number(count, locale)}</dd>
        </div>
      ))}
    </dl>
  );
}
