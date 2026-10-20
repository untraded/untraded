// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import { setTone, vote } from "@/app/actions";
import { type Locale, TONES, type Tone } from "@/i18n/locale";
import type { Advice } from "@/lib/api";
import { cn } from "@/lib/cn";
import { mapName, metric } from "@/lib/format";

/** The session's priorities: the finding in the chosen tone, its cost, its rounds to watch. */
export async function Priorities({
  advice,
  sessionId,
  locale,
  tone,
}: {
  advice: Advice[];
  sessionId: string;
  locale: Locale;
  tone: Tone;
}) {
  const t = await getTranslations("advice");
  return (
    <section className="mt-6">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">{t("title")}</h2>
        <form action={setTone} className="flex items-center gap-1 text-xs" aria-label={t("tone")}>
          {TONES.map((option) => (
            <button
              key={option}
              type="submit"
              name="tone"
              value={option}
              className={cn(
                "rounded px-2 py-0.5",
                option === tone ? "bg-zinc-800 text-white" : "text-zinc-500 hover:text-zinc-200",
              )}
            >
              {t(option)}
            </button>
          ))}
        </form>
      </div>
      {advice.length === 0 ? (
        <p className="text-sm text-zinc-400">{t("none")}</p>
      ) : (
        <ol className="space-y-3">
          {advice.map((item) => (
            <Priority key={item.id} item={item} sessionId={sessionId} locale={locale} tone={tone} />
          ))}
        </ol>
      )}
    </section>
  );
}

async function Priority({
  item,
  sessionId,
  locale,
  tone,
}: {
  item: Advice;
  sessionId: string;
  locale: Locale;
  tone: Tone;
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
  return (
    <li className="rounded border border-zinc-700 bg-zinc-900/40 p-4">
      <div className="flex gap-3">
        <span className="text-2xl font-semibold text-zinc-500 tabular-nums">{item.priority}</span>
        <div className="flex-1">
          <p className="font-medium">{text}</p>
          <p className="mt-1 text-xs text-zinc-500">
            {t("cost", { touched: args.rounds_touched, lost: args.rounds_lost })}
          </p>
          <details className="mt-3 text-sm">
            <summary className="cursor-pointer text-zinc-300">
              {t("evidence", { count: item.evidence.length })}
            </summary>
            <p className="mt-2 text-xs text-zinc-500">{t("copy")}</p>
            <ul className="mt-1 space-y-1">
              {item.evidence.map((event) => (
                <li
                  key={`${event.match_id}-${event.tick}`}
                  className="flex flex-wrap items-baseline gap-x-3"
                >
                  <span className="w-20 text-zinc-400">{t("round", { round: event.round })}</span>
                  <span className="w-20 text-zinc-500">
                    {mapName(event.map ?? null)} {event.side ?? ""}
                  </span>
                  <code className="select-all rounded bg-zinc-800 px-1.5 py-0.5 text-xs">
                    demo_gototick {event.goto_tick}
                  </code>
                </li>
              ))}
            </ul>
          </details>
        </div>
        <form action={vote} className="flex flex-col gap-1">
          <input type="hidden" name="advice" value={item.id} />
          <input type="hidden" name="session" value={sessionId} />
          <input type="hidden" name="current" value={item.my_vote ?? 0} />
          <button
            type="submit"
            name="vote"
            value={1}
            aria-pressed={item.my_vote === 1}
            title={t("useful")}
            className={cn(
              "rounded px-2 py-1",
              item.my_vote === 1 ? "bg-win/20" : "opacity-50 hover:opacity-100",
            )}
          >
            👍
          </button>
          <button
            type="submit"
            name="vote"
            value={-1}
            aria-pressed={item.my_vote === -1}
            title={t("notUseful")}
            className={cn(
              "rounded px-2 py-1",
              item.my_vote === -1 ? "bg-loss/20" : "opacity-50 hover:opacity-100",
            )}
          >
            👎
          </button>
        </form>
      </div>
    </li>
  );
}
