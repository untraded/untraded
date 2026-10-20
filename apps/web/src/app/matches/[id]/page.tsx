// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import { ResultBadge } from "@/components/result-badge";
import type { Locale } from "@/i18n/locale";
import { getMatch, type MatchDetail, type Player, type Round } from "@/lib/api";
import { cn } from "@/lib/cn";
import { dateTime, mapName, number, percent } from "@/lib/format";

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const match = await getMatch((await params).id);
  return { title: match ? mapName(match.map) : "Untraded" };
}

export default async function MatchPage({ params }: { params: Promise<{ id: string }> }) {
  const match = await getMatch((await params).id);
  if (!match) redirect("/");
  const t = await getTranslations("match");
  const locale = (await getLocale()) as Locale;
  const ready = match.status === "ready";
  return (
    <article>
      <Link href="/matches" className="text-sm text-zinc-400 hover:text-white">
        ← {t("back")}
      </Link>
      <header className="mt-4 flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <h1 className="text-2xl font-semibold">{mapName(match.map)}</h1>
        <p className="text-3xl font-semibold tabular-nums">
          {match.score_a ?? "–"} <span className="text-zinc-600">:</span> {match.score_b ?? "–"}
        </p>
        <ResultBadge result={match.my_result} status={match.status} />
        <p className="text-sm text-zinc-400">{dateTime(match.played_at, locale)}</p>
      </header>

      {!ready && <p className="mt-6 text-zinc-400">{match.error ?? t("notReady")}</p>}
      {match.unavailable.length > 0 && (
        <p className="mt-2 text-xs text-zinc-500">
          {t("missing", { items: match.unavailable.join(", ") })}
        </p>
      )}

      {ready && (
        <>
          <Rounds rounds={match.rounds} label={t("rounds")} overtime={t("overtime")} />
          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            {(["A", "B"] as const).map((team) => (
              <TeamTable key={team} match={match} team={team} locale={locale} />
            ))}
          </div>
        </>
      )}
    </article>
  );
}

function Rounds({ rounds, label, overtime }: { rounds: Round[]; label: string; overtime: string }) {
  return (
    <section className="mt-8">
      <h2 className="mb-2 text-sm font-medium text-zinc-400">{label}</h2>
      <ol className="flex flex-wrap gap-1">
        {rounds.map((round) => (
          <li
            key={round.round}
            title={`${round.round} · ${round.winner_side ?? "?"} · ${round.reason}${round.is_overtime ? ` · ${overtime}` : ""}`}
            className={cn(
              "flex h-8 w-7 flex-col items-center justify-center rounded text-[10px] tabular-nums",
              round.winner_team === "A" ? "bg-ct/20" : "bg-t/20",
              round.winner_side === "CT" ? "text-ct" : "text-t",
            )}
          >
            <span className="font-semibold">{round.round}</span>
            <span>{round.winner_team ?? "–"}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

async function TeamTable({
  match,
  team,
  locale,
}: {
  match: MatchDetail;
  team: "A" | "B";
  locale: Locale;
}) {
  const t = await getTranslations("match");
  const m = await getTranslations("matches");
  const players = match.players.filter((p: Player) => p.team === team);
  const name =
    (team === "A" ? match.team_a_name : match.team_b_name) ?? t(team === "A" ? "teamA" : "teamB");
  const score = team === "A" ? match.score_a : match.score_b;
  return (
    <section className="overflow-x-auto rounded border border-zinc-800">
      <h2 className="flex items-baseline justify-between bg-zinc-900 px-3 py-2 text-sm">
        <span className="font-medium">
          {name}{" "}
          <span className="text-xs text-zinc-500">
            {t(team === "A" ? "startedCt" : "startedT")}
          </span>
        </span>
        <span className="text-lg font-semibold tabular-nums">{score ?? "–"}</span>
      </h2>
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-zinc-500">
          <tr>
            <th className="px-3 py-1.5 font-medium">{t("player")}</th>
            <th className="px-2 py-1.5 text-right font-medium">{t("kills")}</th>
            <th className="px-2 py-1.5 text-right font-medium">{t("deaths")}</th>
            <th className="px-2 py-1.5 text-right font-medium">{m("adr")}</th>
            <th className="px-2 py-1.5 text-right font-medium">{m("kast")}</th>
            <th className="px-2 py-1.5 text-right font-medium" title={m("untraded")}>
              UD
            </th>
            <th className="px-3 py-1.5 text-right font-medium">{m("rating")}</th>
          </tr>
        </thead>
        <tbody>
          {players.map((player) => (
            <tr key={player.steam_id} className="border-t border-zinc-800/70">
              <td className="max-w-40 truncate px-3 py-1.5">{player.name}</td>
              <td className="px-2 py-1.5 text-right">{number(player.line.kills, locale)}</td>
              <td className="px-2 py-1.5 text-right">{number(player.line.deaths, locale)}</td>
              <td className="px-2 py-1.5 text-right">{number(player.line.adr, locale)}</td>
              <td className="px-2 py-1.5 text-right">{percent(player.line.kast, locale)}</td>
              <td className="px-2 py-1.5 text-right">
                {number(player.line.untraded_deaths, locale)}
              </td>
              <td className="px-3 py-1.5 text-right font-medium">
                {number(player.line.hltv1, locale, 2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
