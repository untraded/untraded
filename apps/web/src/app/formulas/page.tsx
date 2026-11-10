// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronRight, ExternalLink, Search } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getLocale, getTranslations } from "next-intl/server";
import { Better } from "@/components/formulas/better";
import { FoldPanel } from "@/components/formulas/fold-panel";
import { Inline } from "@/components/formulas/inline";
import { Button } from "@/components/ui/button";
import type { Locale } from "@/i18n/locale";
import type { MetricDoc } from "@/lib/metric-docs";
import { englishDocs, metricCatalog } from "@/lib/metric-docs-files";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("formulas"))("title") };
}

const SPEC = "https://github.com/untraded/untraded/blob/main/docs/metrics-v1.md";

/** The columns of a family's rows from 768 px: name, id, unit, which way is better, chevron. */
const ROW = "md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)_8.5rem_7.5rem_1rem]";

/** Whether a metric answers a search: its name in either language, its id or its definition. */
function matches(doc: MetricDoc, english: MetricDoc | undefined, query: string): boolean {
  const q = query.toLocaleLowerCase();
  return [doc.name, english?.name ?? "", doc.id, ...doc.definition].some((text) =>
    text.toLocaleLowerCase().includes(q),
  );
}

/**
 * Every metric's formula, by family: one folding panel per family, folded so one opens only the
 * one of interest; a search opens the families that hold a match. Each row opens the metric's
 * page. The conventions every metric shares close the list.
 */
export default async function Formulas({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const [{ q }, t, locale] = await Promise.all([
    searchParams,
    getTranslations("formulas"),
    getLocale() as Promise<Locale>,
  ]);
  const query = (typeof q === "string" ? q : "").trim().slice(0, 80);
  const { conventions, families } = metricCatalog(locale);
  const english = englishDocs();
  const total = families.reduce((sum, f) => sum + f.docs.length, 0);
  const shown = families
    .map((f) => ({
      ...f,
      docs: query ? f.docs.filter((d) => matches(d, english.get(d.id), query)) : f.docs,
    }))
    .filter((f) => f.docs.length > 0);
  const count = shown.reduce((sum, f) => sum + f.docs.length, 0);

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
        <p className="max-w-[56ch] text-sm text-pretty text-muted-foreground">{t("lead")}</p>
      </header>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <search className="w-full max-w-md">
          <form action="/formulas" className="flex items-center gap-2">
            <label className="flex h-9 min-w-0 flex-1 items-center gap-2 rounded-md border border-input bg-card px-2.5 focus-within:outline-2 focus-within:outline-ring">
              <Search aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
              <span className="sr-only">{t("search")}</span>
              <input
                type="search"
                name="q"
                defaultValue={query}
                placeholder={t("searchPlaceholder")}
                autoComplete="off"
                spellCheck={false}
                className="min-w-0 flex-1 bg-transparent text-sm outline-none"
              />
            </label>
            <Button type="submit" variant="outline">
              {t("searchButton")}
            </Button>
          </form>
        </search>
        <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[0.8125rem] text-muted-foreground">
          <span className="tabular-nums">{t("count", { shown: count, total })}</span>
          {query && (
            <Link href="/formulas" className="text-link underline underline-offset-3">
              {t("clear")}
            </Link>
          )}
          <a
            href={SPEC}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-link underline underline-offset-3"
          >
            {t("spec")}
            <ExternalLink aria-hidden="true" className="size-3.5" />
          </a>
        </p>
      </div>

      {count === 0 && (
        <p className="rounded-lg border border-dashed border-border px-3.5 py-3 text-sm text-muted-foreground">
          {t("noResult", { query })}
        </p>
      )}

      {shown.length > 0 && (
        <div className="flex flex-col gap-2">
          {shown.map((family) => (
            <FoldPanel
              key={family.prefix}
              title={family.title}
              aside={t("familyCount", { count: family.docs.length })}
              open={Boolean(query)}
            >
              {/* The columns' names, for the eye only: each row is one link, read as a whole. */}
              <div
                aria-hidden="true"
                className={`hidden gap-x-3 border-b border-line-soft px-3.5 py-1.5 text-[0.6875rem] text-muted-foreground md:grid ${ROW}`}
              >
                <span>{t("columns.metric")}</span>
                <span>{t("columns.id")}</span>
                <span>{t("columns.unit")}</span>
                <span>{t("columns.better")}</span>
              </div>
              <ul>
                {family.docs.map((doc) => (
                  <li key={doc.id} className="border-t border-line-soft first:border-t-0">
                    <Link
                      href={`/formulas/${encodeURIComponent(doc.id)}`}
                      className={`grid grid-cols-[minmax(0,1fr)_auto_1rem] items-center gap-x-3 gap-y-0.5 px-3.5 py-2 text-sm hover:bg-muted md:py-1.5 ${ROW}`}
                    >
                      <span className="font-medium">{doc.name}</span>
                      <code
                        translate="no"
                        className="col-start-1 row-start-2 truncate font-mono text-xs text-muted-foreground md:col-start-2 md:row-start-1"
                      >
                        {doc.id}
                      </code>
                      <span className="hidden text-[0.8125rem] text-muted-foreground md:block">
                        {t.has(`units.${doc.unit}`) ? t(`units.${doc.unit}`) : doc.unit}
                      </span>
                      <span className="col-start-2 row-span-2 row-start-1 text-right text-xs text-muted-foreground md:col-start-4 md:row-span-1 md:text-left">
                        <Better
                          better={doc.better}
                          label={
                            t.has(`betterShort.${doc.better}`)
                              ? t(`betterShort.${doc.better}`)
                              : doc.better
                          }
                        />
                      </span>
                      <ChevronRight
                        aria-hidden="true"
                        className="col-start-3 row-span-2 row-start-1 size-4 text-muted-foreground md:col-start-5 md:row-span-1"
                      />
                    </Link>
                  </li>
                ))}
              </ul>
            </FoldPanel>
          ))}
        </div>
      )}

      <FoldPanel id="conventions" title={t("conventions")}>
        <ul className="flex list-disc flex-col gap-1.5 py-3 pr-3.5 pl-8 text-sm leading-relaxed marker:text-muted-foreground">
          {conventions.map((c) => (
            <li key={c} className="max-w-[56ch]">
              <Inline text={c} />
            </li>
          ))}
        </ul>
      </FoldPanel>

      <p className="text-xs text-muted-foreground">{t("source")}</p>
    </section>
  );
}
