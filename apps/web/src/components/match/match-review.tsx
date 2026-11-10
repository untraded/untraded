// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { buttonVariants } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type { MatchDetail } from "@/lib/api";
import { cn } from "@/lib/cn";
import { momentHref, type PriorityInMatch, sideOf, wonRound } from "@/lib/match";

/**
 * What to review in this match, beside the figures: the priorities of the match's session that
 * flag rounds of it, each with its name, how many of its rounds are here (and how many were lost)
 * and a button to the 2D viewer on its first moment in the match. Only the first button is the
 * yellow action; the other flagged rounds are framed in the rounds strip below. Without a
 * session, or without a priority touching the match, says so.
 */
export async function MatchReview({
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
    <Panel
      title={t("review.title")}
      aside={
        session && (
          <Link
            href={`/sessions/${encodeURIComponent(session.id)}`}
            className="text-link underline underline-offset-3"
          >
            {t("report", { date: session.day })}
          </Link>
        )
      }
      flush
    >
      {priorities.length === 0 ? (
        <p className="px-3.5 py-3 text-sm text-muted-foreground">
          {session ? t("noPriority") : t("noSession")}
        </p>
      ) : (
        <>
          <ol>
            {priorities.map(({ advice, rounds }, i) => {
              const key = `rules.${advice.rule_id}.label`;
              const name = a.has(key) ? a(key) : advice.rule_id;
              const lost = rounds.filter((r) => wonRound(match, r.round) === false).length;
              const first = rounds[0];
              const won = first ? wonRound(match, first.round) : null;
              const side = first ? sideOf(match, first.round) : null;
              return (
                <li
                  key={advice.id}
                  className="flex flex-col items-start gap-1.5 border-t border-line-soft px-3.5 py-2.5 first:border-t-0"
                >
                  <span className="flex items-baseline gap-2.5 text-sm font-semibold">
                    <span className="grid size-5 shrink-0 place-items-center self-center rounded-[3px] bg-foreground text-xs text-background">
                      {advice.priority}
                    </span>
                    {name}
                  </span>
                  <span className="text-[0.8125rem] text-muted-foreground">
                    {t("inMatch", { rounds: rounds.length, lost })}
                  </span>
                  {first && (
                    <Link
                      href={momentHref(match.id, first.round, { ...first, rule: advice.rule_id })}
                      aria-label={t(side ? "review.label" : "review.labelNoSide", {
                        name,
                        round: first.round,
                        side: side ?? "",
                        result: t(won === null ? "unknown" : won ? "won" : "lost"),
                      })}
                      className={cn(
                        buttonVariants({ variant: i === 0 ? "default" : "outline", size: "sm" }),
                        "mt-0.5",
                      )}
                    >
                      {t("review.button", { round: first.round })}
                    </Link>
                  )}
                </li>
              );
            })}
          </ol>
          <p className="border-t border-line-soft px-3.5 py-2 text-xs text-muted-foreground">
            {t("review.hint")}
          </p>
        </>
      )}
    </Panel>
  );
}
