// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronDown, ExternalLink } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { Better } from "@/components/formulas/better";
import { Inline } from "@/components/formulas/inline";
import type { Locale } from "@/i18n/locale";
import { apiGetOptional, type SessionList, type SessionReport } from "@/lib/api";
import { compare, gapPercent, gapTrend, metric } from "@/lib/format";
import { metricCatalog, metricDoc } from "@/lib/metric-docs-files";

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const doc = metricDoc((await params).id, (await getLocale()) as Locale);
  return { title: doc?.name ?? "Untraded" };
}

/**
 * One metric's formula, from its page of `docs/metrics/`: the definition first, then the parts
 * one can fold away (parameters, example, CS Demo Manager, limits, history). The player's value
 * on their last session comes first when they have one.
 */
export default async function Formula({ params }: Params) {
  const id = (await params).id;
  const locale = (await getLocale()) as Locale;
  const doc = metricDoc(id, locale);
  if (!doc) notFound();
  const t = await getTranslations("formulas");
  const s = await getTranslations("sessions");
  const family = metricCatalog(locale).families.find((f) => f.prefix === doc.family);

  // The last session's value, an extra the page stands without.
  const latest = (await apiGetOptional<SessionList>("/sessions?limit=1&offset=0"))?.items[0];
  const report = latest
    ? await apiGetOptional<SessionReport>(`/sessions/${encodeURIComponent(latest.id)}`)
    : null;
  const mine = report?.metrics.find((c) => c.metric_id === doc.id);
  const compared = mine && report ? compare(mine, report.rounds) : null;
  const moved = compared?.kind === "ranked" ? gapTrend(compared.gap) : null;

  return (
    <article className="flex max-w-3xl flex-col gap-5">
      <nav className="flex flex-wrap items-center gap-x-1.5 text-[0.8125rem] text-muted-foreground">
        <Link href="/formulas" className="text-link underline underline-offset-3">
          {t("title")}
        </Link>
        <span aria-hidden="true">/</span>
        <span>{family?.title ?? doc.family}</span>
      </nav>

      <header className="flex flex-col gap-2.5">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="text-2xl font-semibold md:text-[1.75rem]">{doc.name}</h1>
          <code translate="no" className="font-mono text-sm text-muted-foreground">
            {doc.id}
          </code>
        </div>
        <ul className="flex flex-wrap gap-1.5 text-xs">
          <Chip>{t("version", { version: doc.version })}</Chip>
          <Chip>{t.has(`units.${doc.unit}`) ? t(`units.${doc.unit}`) : doc.unit}</Chip>
          <Chip>
            <Better
              better={doc.better}
              label={t.has(`better.${doc.better}`) ? t(`better.${doc.better}`) : doc.better}
            />
          </Chip>
          {doc.reads.length > 0 && <Chip>{t("reads", { tables: doc.reads.join(", ") })}</Chip>}
          {doc.code && (
            <li>
              <a
                href={doc.code.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-6 items-center gap-1 rounded-[3px] border border-border bg-card px-2 text-link underline underline-offset-3"
              >
                {t("code")}
                <ExternalLink aria-hidden="true" className="size-3" />
              </a>
            </li>
          )}
        </ul>
      </header>

      {mine && report && (
        <section
          aria-label={t("yourSession")}
          className="flex flex-wrap items-baseline gap-x-5 gap-y-1 rounded-lg border border-dashed border-border px-4 py-3"
        >
          <span className="text-[0.8125rem] text-muted-foreground">{t("yourSession")}</span>
          <span className="text-lg font-semibold tabular-nums">
            {metric(mine.session, mine.unit, mine.basis, locale)}
          </span>
          <span className="text-[0.8125rem] text-muted-foreground tabular-nums">
            {s("vsReference", { value: metric(mine.reference, mine.unit, mine.basis, locale) })}
          </span>
          {moved && compared && (
            <span
              className={
                moved === "better"
                  ? "text-[0.8125rem] text-win"
                  : moved === "worse"
                    ? "text-[0.8125rem] text-loss"
                    : "text-[0.8125rem] text-muted-foreground"
              }
            >
              <span aria-hidden="true">
                {moved === "better" ? "▲" : moved === "worse" ? "▼" : "="}{" "}
              </span>
              {gapPercent(compared.gap, locale)}
            </span>
          )}
          <Link
            href={`/sessions/${report.id}`}
            className="ml-auto text-[0.8125rem] text-link underline underline-offset-3"
          >
            {t("openReport")}
          </Link>
        </section>
      )}

      <section aria-labelledby="definition" className="flex flex-col gap-2">
        <h2 id="definition" className="text-[0.8125rem] font-medium text-muted-foreground">
          {t("definition")}
        </h2>
        <div className="flex flex-col gap-2 rounded-lg border border-border bg-card px-4 py-3.5 text-[0.9375rem] leading-relaxed">
          {doc.definition.map((p) => (
            <p key={p}>
              <Inline text={p} />
            </p>
          ))}
        </div>
      </section>

      {doc.params.length > 0 && (
        <Part title={t("parameters")} open>
          <ul className="flex flex-col">
            {doc.params.map((p) => (
              <li
                key={p.key}
                className="flex flex-col gap-1 border-t border-line-soft py-2.5 text-sm first:border-t-0 first:pt-0 last:pb-0 md:grid md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)] md:gap-x-4"
              >
                <span className="flex flex-wrap items-baseline gap-x-2">
                  <code translate="no" className="font-mono text-[0.8125rem]">
                    {p.key}
                  </code>
                  <span className="text-muted-foreground tabular-nums">
                    <span className="sr-only">{t("default")} </span>
                    {p.value}
                  </span>
                </span>
                <span>
                  <Inline text={p.meaning} />
                </span>
              </li>
            ))}
          </ul>
        </Part>
      )}

      {doc.limits.length > 0 && (
        <Part title={t("limits")} open>
          <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm">
            {doc.limits.map((l) => (
              <li key={l}>
                <Inline text={l} />
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[0.8125rem]">
            <Link href="/formulas#conventions" className="text-link underline underline-offset-3">
              {t("seeConventions")}
            </Link>
          </p>
        </Part>
      )}

      {doc.example && doc.example.rows.length > 1 && (
        <Part title={t("example")}>
          <p className="mb-2 text-[0.8125rem] text-muted-foreground">
            <Inline text={doc.example.where} />
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-[0.8125rem] tabular-nums">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>
                  {doc.example.rows[0]?.map((cell, i) => (
                    // biome-ignore lint/suspicious/noArrayIndexKey: columns of a fixed table
                    <th key={i} scope="col" className="py-1.5 pr-3 font-medium">
                      {cell}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {doc.example.rows.slice(1).map((row, i) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: rows of a fixed table
                  <tr key={i} className="border-t border-line-soft">
                    {row.map((cell, j) => (
                      // biome-ignore lint/suspicious/noArrayIndexKey: columns of a fixed table
                      <td key={j} className="py-1.5 pr-3">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {doc.example.note && (
            <p className="mt-2 text-xs text-muted-foreground">{doc.example.note}</p>
          )}
        </Part>
      )}

      {doc.csdm && (
        <Part title={t("csdm")}>
          <p className="text-sm">
            <Inline text={doc.csdm} />
          </p>
        </Part>
      )}

      {doc.history.length > 0 && (
        <Part title={t("history")}>
          <ul className="flex flex-col gap-1.5 text-sm">
            {doc.history.map((h) => (
              <li key={h.version} className="grid grid-cols-[3.5rem_minmax(0,1fr)] gap-x-3">
                <span className="font-semibold tabular-nums">{h.version}</span>
                <span>
                  <Inline text={h.text} />
                </span>
              </li>
            ))}
          </ul>
        </Part>
      )}
    </article>
  );
}

function Chip({ children }: { children: ReactNode }) {
  return (
    <li className="inline-flex h-6 items-center rounded-[3px] border border-border bg-card px-2">
      {children}
    </li>
  );
}

/** A part of the page one can fold away. */
function Part({ title, open, children }: { title: string; open?: boolean; children: ReactNode }) {
  return (
    <details open={open} className="group rounded-lg border border-border bg-card">
      <summary className="flex cursor-pointer list-none items-center gap-2.5 rounded-lg px-4 py-2.5 text-sm font-semibold hover:bg-muted [&::-webkit-details-marker]:hidden">
        <ChevronDown
          aria-hidden="true"
          className="size-4 -rotate-90 text-muted-foreground transition-transform group-open:rotate-0"
        />
        {title}
      </summary>
      <div className="border-t border-border px-4 py-3">{children}</div>
    </details>
  );
}
