// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { setTone, vote } from "@/app/actions";
import { Choice } from "@/components/choice";
import { Button } from "@/components/ui/button";
import { type Locale, TONES, type Tone } from "@/i18n/locale";
import type { Advice } from "@/lib/api";
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
        <Choice
          action={setTone}
          name="tone"
          label={t("tone")}
          value={tone}
          options={TONES.map((option) => ({ value: option, label: t(option) }))}
        />
      </div>
      {advice.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("none")}</p>
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
    <li className="rounded border border-border bg-card p-4">
      <div className="flex gap-3">
        <span className="text-2xl font-semibold text-muted-foreground tabular-nums">
          {item.priority}
        </span>
        <div className="flex-1">
          <p className="font-medium">{text}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {t("cost", { touched: args.rounds_touched, lost: args.rounds_lost })}
          </p>
          <details className="mt-3 text-sm">
            <summary className="cursor-pointer text-foreground">
              {t("evidence", { count: item.evidence.length })}
            </summary>
            <p className="mt-2 text-xs text-muted-foreground">{t("copy")}</p>
            <ul className="mt-1 space-y-1">
              {item.evidence.map((event) => (
                <li
                  key={`${event.match_id}-${event.tick}`}
                  className="flex flex-wrap items-baseline gap-x-3"
                >
                  <span className="w-20 text-muted-foreground">
                    {t("round", { round: event.round })}
                  </span>
                  <span className="w-20 text-muted-foreground">
                    {mapName(event.map ?? null)} {event.side ?? ""}
                  </span>
                  <code className="select-all rounded bg-muted px-1.5 py-0.5 text-xs">
                    demo_gototick {event.goto_tick}
                  </code>
                </li>
              ))}
            </ul>
          </details>
          <Actions ids={args.actions} title={t("actionsTitle")} />
        </div>
        <form action={vote} className="flex flex-col gap-1">
          <input type="hidden" name="advice" value={item.id} />
          <input type="hidden" name="session" value={sessionId} />
          <input type="hidden" name="current" value={item.my_vote ?? 0} />
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
    </li>
  );
}

/** The actions of a priority, from the catalog (`messages/*.json`, `actions`): drills and
 * in-game adjustments. An action missing from the catalog is not shown. */
async function Actions({ ids, title }: { ids: string[]; title: string }) {
  const t = await getTranslations("actions");
  const known = ids.filter((id) => t.has(`${id}.title`));
  if (known.length === 0) return null;
  return (
    <div className="mt-3">
      <p className="text-xs font-medium text-muted-foreground">{title}</p>
      <ul className="mt-1 space-y-2 text-sm">
        {known.map((id) => (
          <li key={id}>
            <span className="mr-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
              {t(`kinds.${id.split(".")[0]}`)}
            </span>
            <span className="font-medium">{t(`${id}.title`)}</span>
            <p className="mt-0.5 text-muted-foreground">{t(`${id}.how`)}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
