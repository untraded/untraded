// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ExternalLink } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import { Suspense } from "react";
import { Better } from "@/components/formulas/better";
import { FormulaContext, YourSession, YourSessionSkeleton } from "@/components/formulas/context";
import { ExampleTable } from "@/components/formulas/example-table";
import { Inline } from "@/components/formulas/inline";
import { Panel } from "@/components/ui/panel";
import type { Locale } from "@/i18n/locale";
import { getMe } from "@/lib/api";
import { metricCatalog, metricDoc } from "@/lib/metric-docs-files";

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const doc = metricDoc((await params).id, (await getLocale()) as Locale);
  // No title of its own for an unknown metric: the 404 keeps the site's.
  return doc ? { title: doc.name } : {};
}

/** The measure of running text: about 70 characters of IBM Plex Sans a line. */
const PROSE = "max-w-[56ch]";

/**
 * One metric's formula, from its page of `docs/metrics/`. The context bar names it (family,
 * version, unit, which way is better) with the player's value on their last session; then the
 * definition, parameters, limits and example in the reading column, and what one checks rather
 * than reads (the code, CS Demo Manager, the history) beside it.
 */
export default async function Formula({ params }: Params) {
  const [{ id }, locale] = await Promise.all([params, getLocale() as Promise<Locale>]);
  const doc = metricDoc(id, locale);
  if (!doc) notFound();
  // `getMe` is already read by the layout for this request (the API calls are cached per request).
  const [t, me] = await Promise.all([getTranslations("formulas"), getMe()]);
  const family = metricCatalog(locale).families.find((f) => f.prefix === doc.family);
  const unit = t.has(`units.${doc.unit}`) ? t(`units.${doc.unit}`) : doc.unit;
  const better = t.has(`better.${doc.better}`) ? t(`better.${doc.better}`) : doc.better;

  return (
    <>
      <FormulaContext
        name={doc.name}
        id={doc.id}
        family={family?.title ?? doc.family}
        version={doc.version}
        unit={unit}
        better={<Better better={doc.better} label={better} />}
        label={t("context.label")}
      >
        {/* The player's value is there for a signed-in player whose last session has the
            metric: for them, a place of its size while it loads; nothing for a visitor. */}
        <Suspense fallback={me ? <YourSessionSkeleton /> : null}>
          <YourSession id={doc.id} locale={locale} />
        </Suspense>
      </FormulaContext>

      <article className="flex flex-col gap-4">
        <nav aria-label={t("context.trail")} className="text-[0.8125rem] text-muted-foreground">
          <Link href="/formulas" className="hover:text-foreground">
            <span aria-hidden="true">←</span> {t("back")}
          </Link>
        </nav>

        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,40rem)_18.75rem] lg:gap-6">
          <div className="flex min-w-0 flex-col gap-4">
            <Panel title={t("definition")} bodyClassName="flex flex-col gap-3 px-4 py-3.5">
              {doc.definition.map((p) => (
                <p key={p} className={`${PROSE} text-[0.9375rem] leading-relaxed text-pretty`}>
                  <Inline text={p} />
                </p>
              ))}
            </Panel>

            {doc.params.length > 0 && (
              <Panel title={t("parameters")} aside={t("default")} flush>
                <dl>
                  {doc.params.map((p) => (
                    <div
                      key={p.key}
                      className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 border-t border-line-soft px-3.5 py-2.5 text-sm first:border-t-0"
                    >
                      <dt className="min-w-0">
                        <code translate="no" className="font-mono text-[0.8125rem] break-all">
                          {p.key}
                        </code>
                      </dt>
                      <dd className="col-start-2 row-start-1 text-right font-semibold tabular-nums">
                        <span className="sr-only">{t("default")} </span>
                        {p.value}
                      </dd>
                      <dd className={`${PROSE} col-span-2 leading-relaxed text-muted-foreground`}>
                        <Inline text={p.meaning} />
                      </dd>
                    </div>
                  ))}
                </dl>
              </Panel>
            )}

            {doc.limits.length > 0 && (
              <Panel title={t("limits")} bodyClassName="flex flex-col gap-2.5 px-4 py-3.5">
                <ul className="flex list-disc flex-col gap-2 pl-4 text-sm leading-relaxed marker:text-muted-foreground">
                  {doc.limits.map((l) => (
                    <li key={l} className={PROSE}>
                      <Inline text={l} />
                    </li>
                  ))}
                </ul>
                <p className="text-[0.8125rem]">
                  <Link
                    href="/formulas#conventions"
                    className="text-link underline underline-offset-3"
                  >
                    {t("seeConventions")}
                  </Link>
                </p>
              </Panel>
            )}

            {doc.example && doc.example.rows.length > 1 && (
              <Panel title={t("example")} flush>
                <p
                  className={`${PROSE} border-b border-line-soft px-3.5 py-2.5 text-[0.8125rem] leading-relaxed text-muted-foreground`}
                >
                  <Inline text={doc.example.where} />
                </p>
                <ExampleTable rows={doc.example.rows} label={t("example")} />
                {doc.example.note && (
                  <p
                    className={`${PROSE} border-t border-line-soft px-3.5 py-2.5 text-xs leading-relaxed text-muted-foreground`}
                  >
                    {doc.example.note}
                  </p>
                )}
              </Panel>
            )}
          </div>

          <aside className="flex min-w-0 flex-col gap-4">
            {(doc.code || doc.reads.length > 0) && (
              <Panel
                title={t("implementation.title")}
                bodyClassName="flex flex-col gap-2.5 text-sm"
              >
                {doc.reads.length > 0 && (
                  <div className="flex flex-col gap-1">
                    <p className="text-xs text-muted-foreground">{t("implementation.reads")}</p>
                    <ul className="flex flex-wrap gap-1.5">
                      {doc.reads.map((table) => (
                        <li key={table}>
                          <code
                            translate="no"
                            className="rounded-[3px] bg-muted px-1.5 py-0.5 font-mono text-xs"
                          >
                            {table}
                          </code>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {doc.code && (
                  <a
                    href={doc.code.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 self-start text-link underline underline-offset-3"
                  >
                    {t("code")}
                    <ExternalLink aria-hidden="true" className="size-3.5" />
                  </a>
                )}
              </Panel>
            )}

            {doc.csdm && (
              <Panel title={t("csdm")}>
                <p className="text-sm leading-relaxed">
                  <Inline text={doc.csdm} />
                </p>
              </Panel>
            )}

            {doc.history.length > 0 && (
              <Panel title={t("history")} flush>
                <ol>
                  {doc.history.map((h) => (
                    <li
                      key={h.version}
                      className="grid grid-cols-[3.5rem_minmax(0,1fr)] gap-x-3 border-t border-line-soft px-3.5 py-2 text-sm first:border-t-0"
                    >
                      <span className="font-semibold tabular-nums">{h.version}</span>
                      <span className="leading-relaxed">
                        <Inline text={h.text} />
                      </span>
                    </li>
                  ))}
                </ol>
              </Panel>
            )}
          </aside>
        </div>
      </article>
    </>
  );
}
