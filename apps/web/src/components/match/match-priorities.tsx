// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import type { MatchDetail } from "@/lib/api";
import { cn } from "@/lib/cn";
import { type PriorityInMatch, sideOf, wonRound } from "@/lib/match";

/**
 * The priorities of the match's session that flag rounds of this match: for each, its name, how
 * many of its rounds are here, and those rounds as boxes that open the 2D viewer on the moment.
 * Without a session, or without a priority touching the match, says so.
 */
export async function MatchPriorities({
  match,
  priorities,
  session,
}: {
  match: MatchDetail;
  priorities: PriorityInMatch[];
  /** The report the priorities come from; `null` when the match is in no session yet. */
  session: { id: string; day: string } | null;
}) {
  const t = await getTranslations("match");
  const a = await getTranslations("advice");
  return (
    <section aria-labelledby="match-priorities" className="flex flex-col gap-2">
      <h2 id="match-priorities" className="text-[0.8125rem] font-medium text-muted-foreground">
        {t("priorities")}
        {session && (
          <>
            {" · "}
            <Link
              href={`/sessions/${session.id}`}
              className="text-link underline underline-offset-3"
            >
              {t("report", { date: session.day })}
            </Link>
          </>
        )}
      </h2>
      {priorities.length === 0 ? (
        <p className="rounded-md border border-border bg-card p-4 text-sm text-muted-foreground">
          {session ? t("noPriority") : t("noSession")}
        </p>
      ) : (
        <>
          <ol className="flex flex-col rounded-md border border-border bg-card">
            {priorities.map(({ advice, rounds }) => {
              const key = `rules.${advice.rule_id}.label`;
              const lost = rounds.filter((r) => wonRound(match, r.round) === false).length;
              return (
                <li
                  key={advice.id}
                  className="flex flex-col gap-2.5 border-t border-line-soft px-4 py-3 first:border-t-0"
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                    <span className="flex items-baseline gap-2.5 font-semibold">
                      <span className="grid size-5 shrink-0 place-items-center self-center rounded-[3px] bg-foreground text-xs text-background">
                        {advice.priority}
                      </span>
                      {a.has(key) ? a(key) : advice.rule_id}
                    </span>
                    <span className="text-[0.8125rem] text-muted-foreground">
                      {t("inMatch", { rounds: rounds.length, lost })}
                    </span>
                  </div>
                  <ul className="flex flex-wrap gap-1">
                    {rounds.map((flagged) => {
                      const side = sideOf(match, flagged.round);
                      const won = wonRound(match, flagged.round);
                      return (
                        <li key={flagged.round}>
                          <Link
                            href={`/matches/${match.id}/rounds/${flagged.round}?t=${flagged.tick}`}
                            aria-label={t("flagged", {
                              round: flagged.round,
                              side: side ?? "",
                              result: t(won === null ? "unknown" : won ? "won" : "lost"),
                            })}
                            className={cn(
                              "flex h-10 w-11 flex-col items-center justify-center rounded-[2px] border border-border text-xs leading-tight font-semibold shadow-[inset_0_0_0_2px_var(--foreground)] hover:bg-foreground hover:text-background focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                              won && "bg-muted",
                              side === "CT" && "border-b-[3px] border-b-side-ct",
                              side === "T" && "border-b-[3px] border-b-side-t",
                            )}
                          >
                            {flagged.round}
                            <span className="text-[0.625rem] font-normal">{side}</span>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                </li>
              );
            })}
          </ol>
          <p className="text-xs text-muted-foreground">{t("flaggedHint")}</p>
        </>
      )}
    </section>
  );
}
