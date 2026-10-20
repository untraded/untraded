// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronDown, Compass, Dumbbell, ThumbsDown, ThumbsUp } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { setTone, vote } from "@/app/actions";
import { Choice } from "@/components/choice";
import { RoundStrip, type StripCell } from "@/components/round-strip";
import { Button } from "@/components/ui/button";
import { type Locale, TONES, type Tone } from "@/i18n/locale";
import type { Advice, AdviceEvent, MatchDetail } from "@/lib/api";
import { mapName, metric, score } from "@/lib/format";

/**
 * The session's priorities, the first one open: the finding in the chosen tone and its cost, then
 * the rounds to review on their match's strip, what to do, and the vote.
 */
export async function Priorities({
  advice,
  sessionId,
  locale,
  tone,
  hasReference,
  matches,
}: {
  advice: Advice[];
  sessionId: string;
  locale: Locale;
  tone: Tone;
  hasReference: boolean;
  /** The matches the evidence comes from, to draw their rounds. */
  matches: Map<string, MatchDetail>;
}) {
  const t = await getTranslations("advice");
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{t("title")}</h2>
        <Choice
          action={setTone}
          name="tone"
          label={t("tone")}
          value={tone}
          options={TONES.map((option) => ({ value: option, label: t(option) }))}
        />
      </div>
      {advice.length === 0 ? (
        <p className="rounded-lg border border-border bg-card p-4 text-muted-foreground">
          {hasReference ? t("none") : t("noReference")}
        </p>
      ) : (
        <ol className="flex flex-col gap-3">
          {advice.map((item, index) => (
            <Priority
              key={item.id}
              item={item}
              open={index === 0}
              sessionId={sessionId}
              locale={locale}
              tone={tone}
              matches={matches}
            />
          ))}
        </ol>
      )}
    </section>
  );
}

async function Priority({
  item,
  open,
  sessionId,
  locale,
  tone,
  matches,
}: {
  item: Advice;
  open: boolean;
  sessionId: string;
  locale: Locale;
  tone: Tone;
  matches: Map<string, MatchDetail>;
}) {
  const t = await getTranslations("advice");
  const { args } = item;
  const basis = args.basis === "pattern" ? "value" : args.basis;
  const text = t(`rules.${item.rule_id}.${tone}`, {
    events: args.events,
    session: metric(args.session, args.unit, basis, locale),
    reference: metric(args.reference, args.unit, basis, locale),
    zone: args.zone ?? "",
    map: mapName(args.map ?? null),
    side: args.side ?? "",
    history: args.history_events ?? 0,
  });
  const byMatch = new Map<string, AdviceEvent[]>();
  for (const event of item.evidence) {
    byMatch.set(event.match_id, [...(byMatch.get(event.match_id) ?? []), event]);
  }
  return (
    <li>
      <details open={open} className="group rounded-lg border border-border bg-card">
        <summary className="grid cursor-pointer list-none rounded-lg hover:bg-muted/40 grid-cols-[1.25rem_minmax(0,1fr)_1.25rem] gap-x-3 gap-y-0.5 p-4 sm:px-5 [&::-webkit-details-marker]:hidden">
          <span className="text-[1.0625rem] font-semibold text-muted-foreground">
            {item.priority}
          </span>
          <span className="text-base leading-snug font-semibold text-pretty sm:text-[1.0625rem]">
            {text}
          </span>
          <ChevronDown
            aria-hidden="true"
            className="mt-1 size-4 text-muted-foreground transition-transform group-open:rotate-180"
          />
          <span className="col-start-2 text-[0.8125rem] text-muted-foreground">
            {t("costLong", { touched: args.rounds_touched, lost: args.rounds_lost })}
          </span>
        </summary>
        <div className="flex flex-col gap-5 px-4 pb-4 sm:pr-5 sm:pl-12">
          <div className="flex flex-col gap-3">
            <p className="text-[0.8125rem] font-medium text-muted-foreground">
              {t("evidence", { count: item.evidence.length })}
            </p>
            {[...byMatch].map(([matchId, events]) => (
              <Evidence key={matchId} events={events} match={matches.get(matchId)} />
            ))}
          </div>
          <Actions ids={args.actions} title={t("actionsTitle")} />
          <form
            action={vote}
            className="flex items-center justify-end gap-1 border-t border-line-soft pt-2.5 text-[0.8125rem] text-muted-foreground"
          >
            <input type="hidden" name="advice" value={item.id} />
            <input type="hidden" name="session" value={sessionId} />
            <input type="hidden" name="current" value={item.my_vote ?? 0} />
            <span className="mr-1">{t("helpful")}</span>
            <Button
              type="submit"
              name="vote"
              value={1}
              variant="ghost"
              size="icon-sm"
              aria-pressed={item.my_vote === 1}
              aria-label={t("useful")}
              title={t("useful")}
            >
              <ThumbsUp aria-hidden="true" />
            </Button>
            <Button
              type="submit"
              name="vote"
              value={-1}
              variant="ghost"
              size="icon-sm"
              aria-pressed={item.my_vote === -1}
              aria-label={t("notUseful")}
              title={t("notUseful")}
            >
              <ThumbsDown aria-hidden="true" />
            </Button>
          </form>
        </div>
      </details>
    </li>
  );
}

/** The rounds to review in one match: on its strip of rounds when the match is known. */
async function Evidence({
  events,
  match,
}: {
  events: AdviceEvent[];
  match: MatchDetail | undefined;
}) {
  const t = await getTranslations("advice");
  const byRound = new Map(events.map((event) => [event.round, event]));
  const mark = (event: AdviceEvent, side: string, won: boolean | null) => ({
    tick: event.goto_tick,
    label: t("roundLabel", {
      round: event.round,
      side,
      result: won === null ? "" : t(won ? "won" : "lost"),
    }),
    command: t("roundCommand", { round: event.round, side }),
  });
  let cells: StripCell[];
  let title: string;
  if (match && match.rounds.length > 0 && match.my_team) {
    const me = match.my_team;
    cells = match.rounds.map((round, i) => {
      const side = round.ct_team === me ? "CT" : "T";
      const won = round.winner_team === null ? null : round.winner_team === me;
      const event = byRound.get(round.round);
      const previous = match.rounds[i - 1];
      return {
        round: round.round,
        won,
        side,
        half: previous !== undefined && previous.ct_team !== round.ct_team,
        mark: event ? mark(event, side, won) : undefined,
      };
    });
    title = t("stripTitle", {
      map: mapName(match.map),
      score: score(match.score_a, match.score_b, me),
      rounds: match.rounds.length,
    });
  } else {
    // The match is not available: the rounds alone, still with their commands.
    cells = events.map((event) => ({
      round: event.round,
      won: null,
      side: event.side === "CT" || event.side === "T" ? event.side : null,
      half: false,
      mark: mark(event, event.side ?? "", null),
    }));
    title = mapName(events[0]?.map ?? null);
  }
  return (
    <RoundStrip
      title={title}
      legend={t("stripLegend")}
      cells={cells}
      labels={{ copy: t("copyCommand"), copied: t("copied") }}
    />
  );
}

/** The actions of a priority, from the catalog (`messages/*.json`, `actions`): in-game
 * adjustments and drills. An action missing from the catalog is not shown. */
async function Actions({ ids, title }: { ids: string[]; title: string }) {
  const t = await getTranslations("actions");
  const known = ids.filter((id) => t.has(`${id}.title`));
  if (known.length === 0) return null;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-[0.8125rem] font-medium text-muted-foreground">{title}</p>
      <ul className="flex flex-col gap-3">
        {known.map((id) => {
          const kind = id.split(".")[0] ?? "";
          const Icon = kind === "drill" ? Dumbbell : Compass;
          return (
            <li key={id} className="grid grid-cols-[1rem_minmax(0,1fr)] gap-x-2.5">
              <Icon aria-hidden="true" className="mt-1 size-4 text-muted-foreground" />
              <div>
                <span className="font-semibold">{t(`${id}.title`)}</span>{" "}
                <span className="text-[0.8125rem] text-muted-foreground">{t(`kinds.${kind}`)}</span>
                <p className="mt-0.5 max-w-prose text-sm text-muted-foreground">{t(`${id}.how`)}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
