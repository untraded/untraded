// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { CopyCommand } from "@/components/copy-command";
import { ReplayViewer, type ViewerLabels } from "@/components/replay/replay-viewer";
import { buttonVariants } from "@/components/ui/button";
import type { Locale } from "@/i18n/locale";
import { getMatch, getMe } from "@/lib/api";
import { cn } from "@/lib/cn";
import { mapName, score, shortDay } from "@/lib/format";

type Params = {
  params: Promise<{ id: string; round: string }>;
  searchParams: Promise<{ t?: string; e?: string; player?: string; p?: string }>;
};

const STEAM_ID = /^\d{1,20}$/;

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { round } = await params;
  return { title: (await getTranslations("viewer"))("title", { round: Number(round) || 0 }) };
}

/**
 * One round, replayed from above (`?t=` the tick it opens on, `?player=` the player highlighted,
 * by default the signed-in one). The rounds to review of a report open it 5 s before their event,
 * with `?e=` the event's tick and `?p=` the rule of the priority they are evidence for.
 */
export default async function RoundPage({ params, searchParams }: Params) {
  const { id, round: roundParam } = await params;
  const query = await searchParams;
  const number = Number(roundParam);
  if (!Number.isInteger(number) || number < 0) notFound();
  const [me, match] = await Promise.all([getMe(), getMatch(id)]);
  if (!me || !match) redirect("/");
  if (match.status !== "ready") notFound();
  const t = await getTranslations("viewer");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const rounds = match.rounds.map((r) => r.round);
  const round = match.rounds.find((r) => r.round === number);
  if (rounds.length > 0 && !round) notFound();
  const index = rounds.indexOf(number);
  const previous = index > 0 ? rounds[index - 1] : undefined;
  const next = index >= 0 && index < rounds.length - 1 ? rounds[index + 1] : undefined;
  const start = query.t !== undefined && /^\d+$/.test(query.t) ? Number(query.t) : null;
  const event = start !== null && query.e && /^\d+$/.test(query.e) ? Number(query.e) : null;
  const focus = query.player && STEAM_ID.test(query.player) ? query.player : me.steam_id;
  const focusName =
    match.players.find((p) => p.steam_id === focus)?.name ??
    (focus === me.steam_id ? me.display_name : null);
  const won =
    round && match.my_team && round.winner_team ? round.winner_team === match.my_team : null;
  const reasons = t.raw("reasons") as Record<string, string>;
  const reason = round ? reasons[round.reason] : undefined;
  const labels = await viewerLabels(number);
  const command = start !== null ? `demo_gototick ${start}` : null;
  const advice = await getTranslations("advice");
  const rule = query.p && /^[a-z0-9_.]{1,64}$/.test(query.p) ? `rules.${query.p}.label` : null;
  const proof = start !== null && rule && advice.has(rule) ? advice(rule) : null;

  return (
    <article className="flex flex-col gap-3.5">
      <nav className="flex flex-wrap items-center gap-x-1.5 text-[0.8125rem] text-muted-foreground">
        <Link href="/matches" className="text-link underline underline-offset-3">
          {(await getTranslations("matches"))("title")}
        </Link>
        <span aria-hidden="true">/</span>
        <Link href={`/matches/${match.id}`} className="text-link underline underline-offset-3">
          {t("crumb", {
            map: mapName(match.map),
            date: match.played_at ? shortDay(match.played_at, locale, timeZone) : "–",
            score: score(match.score_a, match.score_b, match.my_team),
          })}
        </Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{t("title", { round: number })}</span>
      </nav>
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2.5">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold">
            {t("title", { round: number })}
            {rounds.length > 0 && (
              <span className="ml-2 text-base font-normal text-muted-foreground">
                {t("of", { count: rounds.length })}
              </span>
            )}
          </h1>
          {round?.winner_side && (
            <p className="flex flex-wrap items-center gap-2 text-sm">
              {won !== null && (
                <span
                  className={cn(
                    "rounded-sm px-2 py-0.5 text-xs font-semibold",
                    won ? "bg-win/15" : "bg-loss/15",
                  )}
                >
                  {t(won ? "won" : "lost")}
                </span>
              )}
              <span className="text-muted-foreground">
                {reason
                  ? t("winnerReason", { side: round.winner_side, reason })
                  : t("winner", { side: round.winner_side })}
              </span>
            </p>
          )}
        </div>
        <div className="flex gap-1.5">
          {previous !== undefined && (
            <Link
              href={`/matches/${match.id}/rounds/${previous}`}
              aria-label={t("previousLabel", { round: previous })}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "gap-1")}
            >
              <ChevronLeft aria-hidden="true" />
              {t("previous", { round: previous })}
            </Link>
          )}
          {next !== undefined && (
            <Link
              href={`/matches/${match.id}/rounds/${next}`}
              aria-label={t("nextLabel", { round: next })}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "gap-1")}
            >
              {t("next", { round: next })}
              <ChevronRight aria-hidden="true" />
            </Link>
          )}
        </div>
      </header>
      {command && (
        <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1.5 rounded-lg bg-highlight-soft px-3.5 py-2 text-sm">
          <span>
            {proof && `${t("proofFor", { label: proof })} `}
            {t("focus")} {focusName && t("focusPlayer", { name: focusName })}
          </span>
          <span className="flex flex-wrap items-center gap-2 sm:ml-auto">
            <span className="text-muted-foreground">{t("inGame")}</span>
            <CopyCommand command={command} copy={t("copy", { command })} />
          </span>
        </div>
      )}
      <ReplayViewer
        key={`${match.id}-${number}`}
        matchId={match.id}
        round={number}
        start={start}
        moment={event}
        focus={focus}
        labels={labels}
        locale={locale}
      />
    </article>
  );
}

async function viewerLabels(round: number): Promise<ViewerLabels> {
  const t = await getTranslations("viewer");
  const keep = (key: string) => `{${key}}`;
  return {
    canvas: t("canvas", { round }),
    loading: t("loading"),
    missing: t("missing"),
    failed: t("failed"),
    noGraphics: t("noGraphics"),
    play: t("play"),
    pause: t("pause"),
    back: t("back"),
    forward: t("forward"),
    speed: t("speed"),
    timeline: t("timeline"),
    level: t("level"),
    upper: t("upper"),
    lower: t("lower"),
    freeze: t("freeze"),
    bomb: t("bomb"),
    noRadar: t("noRadar"),
    alive: t("alive", { count: keep("count") }),
    dead: t("dead"),
    kills: t("kills"),
    noKills: t("noKills"),
    headshot: t("headshot"),
    world: t("world"),
    knife: t("knife"),
    c4: t("c4"),
    keys: t("keys"),
    legendKill: t("legendKill"),
    legendBomb: t("legendBomb"),
    legendFocus: t("legendFocus"),
    markPlant: t("markPlant", { time: keep("time") }),
    markFocus: t("markFocus"),
    playMoment: t("playMoment"),
    momentSoon: t("momentSoon", { seconds: keep("seconds") }),
    momentAt: t("momentAt", { time: keep("time") }),
    momentLine: t("momentLine", { when: keep("when"), event: keep("event") }),
    momentKilled: t("momentKilled", {
      victim: keep("victim"),
      attacker: keep("attacker"),
      weapon: keep("weapon"),
    }),
    momentKills: t("momentKills", {
      attacker: keep("attacker"),
      victim: keep("victim"),
      weapon: keep("weapon"),
    }),
    momentOther: t("momentOther"),
    momentDies: t("momentDies", { victim: keep("victim"), cause: keep("cause") }),
    causeBomb: t("causeBomb"),
    causeWorld: t("causeWorld"),
    momentSuicideGrenade: t("momentSuicideGrenade", { victim: keep("victim") }),
    momentSuicide: t("momentSuicide", { victim: keep("victim") }),
    markKill: t("markKill", {
      attacker: keep("attacker"),
      victim: keep("victim"),
      time: keep("time"),
    }),
    winprob: {
      title: t("winprob.title"),
      model: t("winprob.model", { model: keep("model") }),
      method: t("winprob.method"),
      legend: t("winprob.legend"),
      moments: t("winprob.moments"),
      kill: t("winprob.kill", { attacker: keep("attacker"), victim: keep("victim") }),
      plant: t("winprob.plant", { player: keep("player") }),
      defuse: t("winprob.defuse", { player: keep("player") }),
      forSide: t("winprob.forSide", { points: keep("points"), side: keep("side") }),
      seek: t("winprob.seek", { what: keep("what"), time: keep("time") }),
    },
    noWinprob: t("winprob.none"),
  };
}
