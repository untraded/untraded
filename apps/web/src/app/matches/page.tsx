// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import { ResultBadge } from "@/components/result-badge";
import type { Locale } from "@/i18n/locale";
import { getMatches } from "@/lib/api";
import { dateTime, killDiff, mapName, number, percent, score } from "@/lib/format";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("matches"))("title") };
}
const PAGE = 30;

export default async function Matches({
  searchParams,
}: {
  searchParams: Promise<{ offset?: string }>;
}) {
  const offset = Math.max(0, Number((await searchParams).offset ?? 0) || 0);
  const list = await getMatches(offset);
  if (!list) redirect("/");
  const t = await getTranslations("matches");
  const locale = (await getLocale()) as Locale;
  return (
    <section>
      <h1 className="mb-6 text-2xl font-semibold">{t("title")}</h1>
      {list.items.length === 0 ? (
        <p className="text-muted-foreground">{t("empty")}</p>
      ) : (
        <div className="overflow-x-auto rounded border border-border">
          <table className="w-full text-sm">
            <thead className="bg-card text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">{t("date")}</th>
                <th className="px-3 py-2 font-medium">{t("map")}</th>
                <th className="px-3 py-2 font-medium">{t("score")}</th>
                <th className="px-3 py-2 font-medium">{t("result")}</th>
                <th className="px-3 py-2 text-right font-medium">{t("kd")}</th>
                <th className="px-3 py-2 text-right font-medium">{t("adr")}</th>
                <th className="px-3 py-2 text-right font-medium">{t("kast")}</th>
                <th className="px-3 py-2 text-right font-medium">{t("rating")}</th>
              </tr>
            </thead>
            <tbody>
              {list.items.map((match) => (
                <tr key={match.id} className="border-t border-border hover:bg-card">
                  <td className="px-3 py-2 whitespace-nowrap">
                    <Link href={`/matches/${match.id}`} className="hover:underline">
                      {dateTime(match.played_at, locale)}
                    </Link>
                  </td>
                  <td className="px-3 py-2">{mapName(match.map)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {score(match.score_a, match.score_b, match.my_team)}
                  </td>
                  <td className="px-3 py-2">
                    <ResultBadge result={match.my_result} status={match.status} />
                  </td>
                  <td className="px-3 py-2 text-right">{killDiff(match.my_line)}</td>
                  <td className="px-3 py-2 text-right">{number(match.my_line?.adr, locale)}</td>
                  <td className="px-3 py-2 text-right">{percent(match.my_line?.kast, locale)}</td>
                  <td className="px-3 py-2 text-right">
                    {number(match.my_line?.hltv1, locale, 2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <nav className="mt-4 flex justify-between text-sm text-muted-foreground">
        {offset > 0 ? (
          <Link href={`/matches?offset=${Math.max(0, offset - PAGE)}`}>← {t("newer")}</Link>
        ) : (
          <span />
        )}
        {list.items.length === PAGE && (
          <Link href={`/matches?offset=${offset + PAGE}`}>{t("older")} →</Link>
        )}
      </nav>
    </section>
  );
}
