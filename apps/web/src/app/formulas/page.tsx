// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronDown, ChevronRight, ExternalLink, Search } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getLocale, getTranslations } from "next-intl/server";
import { Better } from "@/components/formulas/better";
import { Inline } from "@/components/formulas/inline";
import { Button } from "@/components/ui/button";
import type { Locale } from "@/i18n/locale";
import type { MetricDoc } from "@/lib/metric-docs";
import { metricCatalog, metricDocs } from "@/lib/metric-docs-files";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("formulas"))("title") };
}

const SPEC = "https://github.com/untraded/untraded/blob/main/docs/metrics-v1.md";

/** Whether a metric answers a search: its name in either language, its id or its definition. */
function matches(doc: MetricDoc, english: MetricDoc | undefined, query: string): boolean {
  const q = query.toLocaleLowerCase();
  return [doc.name, english?.name ?? "", doc.id, ...doc.definition].some((text) =>
    text.toLocaleLowerCase().includes(q),
  );
}

/**
 * Every metric's formula, by family, the families folded so one can open only the one of
 * interest; a search opens the families that hold a match. Each row opens the metric's page.
 */
export default async function Formulas({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const query = ((await searchParams).q ?? "").trim().slice(0, 80);
  const t = await getTranslations("formulas");
  const locale = (await getLocale()) as Locale;
  const { conventions, families } = metricCatalog(locale);
  const english = new Map(metricDocs().docs.map((d) => [d.id, d]));
  const total = families.reduce((sum, f) => sum + f.docs.length, 0);
  const shown = families
    .map((f) => ({
      ...f,
      docs: query ? f.docs.filter((d) => matches(d, english.get(d.id), query)) : f.docs,
    }))
    .filter((f) => f.docs.length > 0);
  const count = shown.reduce((sum, f) => sum + f.docs.length, 0);
  const summary =
    "flex cursor-pointer list-none items-center gap-2.5 rounded-lg px-4 py-3 hover:bg-muted [&::-webkit-details-marker]:hidden";

  return (
    <section className="flex flex-col gap-5">
      <header className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
        <p className="max-w-prose text-sm text-muted-foreground">{t("lead")}</p>
      </header>

      <search>
        <form action="/formulas" className="flex max-w-md items-center gap-2">
          <label className="flex h-9 min-w-0 flex-1 items-center gap-2 rounded-md border border-input bg-card px-2.5 focus-within:outline-2 focus-within:outline-ring">
            <Search aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
            <span className="sr-only">{t("search")}</span>
            <input
              type="search"
              name="q"
              defaultValue={query}
              placeholder={t("searchPlaceholder")}
              className="min-w-0 flex-1 bg-transparent text-sm outline-none"
            />
          </label>
          <Button type="submit" variant="outline">
            {t("searchButton")}
          </Button>
          {query && (
            <Link
              href="/formulas"
              className="text-[0.8125rem] text-link underline underline-offset-3"
            >
              {t("clear")}
            </Link>
          )}
        </form>
      </search>

      <p className="flex flex-wrap gap-x-4 gap-y-1 text-[0.8125rem] text-muted-foreground">
        <span>{t("count", { shown: count, total })}</span>
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

      {count === 0 && <p className="text-muted-foreground">{t("noResult", { query })}</p>}

      <div className="flex flex-col gap-2.5">
        {shown.map((family) => (
          <details
            key={family.prefix}
            open={Boolean(query)}
            className="group rounded-lg border border-border bg-card"
          >
            <summary className={summary}>
              <ChevronDown
                aria-hidden="true"
                className="size-4 -rotate-90 text-muted-foreground transition-transform group-open:rotate-0"
              />
              <span className="font-semibold">{family.title}</span>
              <span className="ml-auto text-[0.8125rem] text-muted-foreground">
                {t("familyCount", { count: family.docs.length })}
              </span>
            </summary>
            <ul className="border-t border-border">
              {family.docs.map((doc) => (
                <li key={doc.id} className="border-t border-line-soft first:border-t-0">
                  <Link
                    href={`/formulas/${doc.id}`}
                    className="grid grid-cols-[minmax(0,1fr)_auto_1rem] items-center gap-x-3 gap-y-0.5 px-4 py-2 hover:bg-muted md:grid-cols-[minmax(0,14rem)_minmax(0,1fr)_9rem_6rem_1rem]"
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
          </details>
        ))}
      </div>

      <details id="conventions" className="group rounded-lg border border-border bg-card">
        <summary className={summary}>
          <ChevronDown
            aria-hidden="true"
            className="size-4 -rotate-90 text-muted-foreground transition-transform group-open:rotate-0"
          />
          <span className="font-semibold">{t("conventions")}</span>
        </summary>
        <ul className="flex list-disc flex-col gap-1.5 border-t border-border py-3 pr-4 pl-10 text-sm">
          {conventions.map((c) => (
            <li key={c} className="max-w-prose">
              <Inline text={c} />
            </li>
          ))}
        </ul>
      </details>

      <p className="text-xs text-muted-foreground">{t("source")}</p>
    </section>
  );
}
