// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import type { MatchDetail, Round } from "@/lib/api";
import { cn } from "@/lib/cn";
import { momentHref } from "@/lib/match";

/**
 * Every round of the match, each a link to the 2D viewer: filled = won, the bottom line = the side
 * played, also written above each half; the rounds a priority flags are framed. One row per half
 * on a phone, the whole match on one row on wider screens.
 */
export async function MatchRounds({
  match,
  flagged,
}: {
  match: MatchDetail;
  /** Rounds to review (any priority), with the moment the viewer opens on. */
  flagged: Map<number, { tick: number; event: number; rule: string }>;
}) {
  const t = await getTranslations("match");
  const reasons = (await getTranslations("viewer")).raw("reasons") as Record<string, string>;
  const me = match.my_team;
  const side = (round: Round) => (me ? (round.ct_team === me ? "CT" : "T") : null);

  // Consecutive rounds played on the same side: the halves (and overtime halves).
  const halves: Round[][] = [];
  for (const round of match.rounds) {
    const last = halves.at(-1);
    if (last && last[0]?.ct_team === round.ct_team) last.push(round);
    else halves.push([round]);
  }
  const widest = Math.max(...halves.map((h) => h.length));

  const cell = (round: Round, gap: boolean) => {
    const played = side(round);
    const won = me && round.winner_team ? round.winner_team === me : null;
    const result = t(won === null ? "unknown" : won ? "won" : "lost");
    const moment = flagged.get(round.round);
    const label =
      moment === undefined
        ? t("roundLink", {
            round: round.round,
            side: played ?? "",
            result,
            reason: reasons[round.reason] ?? round.reason,
          })
        : t("roundLinkFlagged", { round: round.round, side: played ?? "", result });
    return (
      <Link
        key={round.round}
        href={
          moment === undefined
            ? `/matches/${match.id}/rounds/${round.round}`
            : momentHref(match.id, round.round, moment)
        }
        aria-label={label}
        title={label}
        className={cn(
          "grid h-[26px] place-items-center rounded-[2px] border border-border text-[0.6875rem] text-muted-foreground hover:border-foreground focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring",
          won && "bg-muted text-foreground",
          played === "CT" && "border-b-[3px] border-b-side-ct",
          played === "T" && "border-b-[3px] border-b-side-t",
          moment !== undefined &&
            "font-semibold text-foreground shadow-[inset_0_0_0_2px_var(--foreground)]",
          gap && "ml-1.5",
        )}
      >
        {round.round}
      </Link>
    );
  };

  return (
    <section aria-labelledby="match-rounds" className="flex flex-col gap-2">
      <div className="flex flex-wrap justify-between gap-x-4 gap-y-1 text-[0.8125rem] text-muted-foreground">
        <h2 id="match-rounds" className="font-medium">
          {t("rounds")}
        </h2>
        <span>
          {t("roundsLegend")}. {t("roundsHint")}
        </span>
      </div>
      <div className="flex flex-col gap-1.5 sm:hidden">
        {halves.map((half) => (
          <div key={half[0]?.round} className="flex flex-col gap-0.5">
            {me && (
              <span
                aria-hidden="true"
                className="text-[0.6875rem] font-semibold text-muted-foreground"
              >
                {half[0] && side(half[0])}
              </span>
            )}
            <div
              className="grid gap-0.5"
              style={{ gridTemplateColumns: `repeat(${widest}, minmax(0, 1fr))` }}
            >
              {half.map((round) => cell(round, false))}
            </div>
          </div>
        ))}
      </div>
      <div className="hidden flex-col gap-1 sm:flex">
        {me && (
          <div
            aria-hidden="true"
            className="grid gap-[3px]"
            style={{ gridTemplateColumns: `repeat(${match.rounds.length}, minmax(0, 1fr))` }}
          >
            {halves.map((half, i) => (
              <span
                key={half[0]?.round}
                style={{ gridColumn: `span ${half.length}` }}
                className={cn(
                  "border-l border-border pl-1 text-[0.6875rem] font-semibold text-muted-foreground",
                  i > 0 && "ml-1.5",
                )}
              >
                {half[0] && side(half[0])}
              </span>
            ))}
          </div>
        )}
        <div
          className="grid gap-[3px]"
          style={{ gridTemplateColumns: `repeat(${match.rounds.length}, minmax(0, 1fr))` }}
        >
          {halves.flatMap((half, i) => half.map((round, j) => cell(round, i > 0 && j === 0)))}
        </div>
      </div>
    </section>
  );
}
