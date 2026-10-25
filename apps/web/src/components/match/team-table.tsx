// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import type { Locale } from "@/i18n/locale";
import type { MatchDetail } from "@/lib/api";
import { cn } from "@/lib/cn";
import { number } from "@/lib/format";

/** One team of the match, compact (K–D, ADR, rating), best rating first, the player's row marked. */
export async function TeamTable({
  match,
  team,
  me,
  locale,
}: {
  match: MatchDetail;
  team: "A" | "B";
  /** The signed-in player's SteamID. */
  me: string;
  locale: Locale;
}) {
  const t = await getTranslations("match");
  const m = await getTranslations("matches");
  const players = match.players
    .filter((p) => p.team === team)
    .sort((x, y) => (y.line.hltv1 ?? -1) - (x.line.hltv1 ?? -1));
  const fallback = match.my_team
    ? t(team === match.my_team ? "yourTeam" : "opponents")
    : t(team === "A" ? "teamA" : "teamB");
  const name = (team === "A" ? match.team_a_name : match.team_b_name) ?? fallback;
  const score = team === "A" ? match.score_a : match.score_b;
  const id = `team-${team}`;
  return (
    <section
      aria-labelledby={id}
      className="overflow-x-auto rounded-md border border-border bg-card"
    >
      <h2 id={id} className="flex items-baseline justify-between gap-3 px-3 py-2 text-sm">
        <span>
          <span className="font-medium">{name}</span>{" "}
          <span className="text-xs text-muted-foreground">
            {t(team === "A" ? "startedCt" : "startedT")}
          </span>
        </span>
        <span className="text-lg font-semibold tabular-nums">{score ?? "–"}</span>
      </h2>
      <table className="w-full text-[0.8125rem] tabular-nums">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-t border-border">
            <th scope="col" className="px-3 py-1.5 text-left font-medium">
              {t("player")}
            </th>
            <th scope="col" className="px-2 py-1.5 text-right font-medium">
              {m("kd")}
            </th>
            <th scope="col" className="px-2 py-1.5 text-right font-medium">
              {m("adr")}
            </th>
            <th scope="col" className="px-3 py-1.5 text-right font-medium">
              {m("rating")}
            </th>
          </tr>
        </thead>
        <tbody>
          {players.map((player) => {
            const mine = player.steam_id === me;
            return (
              <tr
                key={player.steam_id}
                className={cn("border-t border-line-soft", mine && "bg-muted font-semibold")}
              >
                <th
                  scope="row"
                  className={cn(
                    "max-w-40 truncate px-3 py-1.5 text-left",
                    mine ? "font-semibold" : "font-normal",
                  )}
                >
                  {player.name}
                  {mine && (
                    <span className="ml-1.5 text-[0.6875rem] font-medium text-muted-foreground">
                      {t("you")}
                    </span>
                  )}
                </th>
                <td className="px-2 py-1.5 text-right">
                  {number(player.line.kills, locale)}–{number(player.line.deaths, locale)}
                </td>
                <td className="px-2 py-1.5 text-right">{number(player.line.adr, locale)}</td>
                <td className="px-3 py-1.5 text-right">{number(player.line.hltv1, locale, 2)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
