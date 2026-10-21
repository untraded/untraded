// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { ComparisonCard } from "@/components/comparison";
import type { Locale } from "@/i18n/locale";
import { getSessions } from "@/lib/api";
import { dateRange } from "@/lib/format";

const PAGE = 20;

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("sessions"))("title") };
}

export default async function Sessions({
  searchParams,
}: {
  searchParams: Promise<{ offset?: string }>;
}) {
  const offset = Math.max(0, Number((await searchParams).offset ?? 0) || 0);
  const list = await getSessions(offset);
  if (!list) redirect("/");
  const t = await getTranslations("sessions");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  return (
    <section>
      <h1 className="mb-6 text-2xl font-semibold">{t("title")}</h1>
      {list.items.length === 0 && <p className="text-muted-foreground">{t("empty")}</p>}
      <ul className="space-y-4">
        {list.items.map((session) => (
          <li key={session.id}>
            <Link
              href={`/sessions/${session.id}`}
              className="block rounded border border-border p-4 hover:border-muted-foreground"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-medium">
                  {dateRange(session.started_at, session.ended_at, locale, timeZone)}
                </span>
                <span className="text-sm text-muted-foreground">
                  {t("count", { matches: session.matches, rounds: session.rounds })} ·{" "}
                  {t("record", {
                    wins: session.wins,
                    losses: session.losses,
                    ties: session.ties,
                  })}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                {session.headlines.map((c) => (
                  <ComparisonCard
                    key={c.metric_id}
                    comparison={c}
                    locale={locale}
                    perRound={t("perRound")}
                  />
                ))}
              </div>
            </Link>
          </li>
        ))}
      </ul>
      <nav className="mt-4 flex justify-between text-sm text-muted-foreground">
        {offset > 0 ? (
          <Link href={`/sessions?offset=${Math.max(0, offset - PAGE)}`}>← {t("newer")}</Link>
        ) : (
          <span />
        )}
        {list.items.length === PAGE && (
          <Link href={`/sessions?offset=${offset + PAGE}`}>{t("older")} →</Link>
        )}
      </nav>
    </section>
  );
}
