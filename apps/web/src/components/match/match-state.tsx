// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { Check } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { Panel } from "@/components/ui/panel";
import type { MatchDetail } from "@/lib/api";
import { cn } from "@/lib/cn";
import { errorSummary } from "@/lib/match";

/** The steps of the analysis, in their order, by the status that is at that step. */
const STEPS = ["pending", "downloading", "parsing"] as const;
/** What the page shows once the analysis is done, in the page's order. */
const COMING = ["self", "priorities", "rounds", "rating", "sides", "teams"] as const;

/**
 * A match that is not analysed: where its analysis stands and what the page will show once it is
 * done, or why it will not be (failed, unavailable), with the first line of the worker's error as
 * a technical detail. The context bar above already says the map, the mode and the date.
 */
export async function MatchState({ match }: { match: MatchDetail }) {
  const t = await getTranslations("match.state");
  if (match.status === "failed" || match.status === "unavailable") {
    const key = match.status;
    const detail = errorSummary(match.error);
    return (
      <Panel
        title={t(`${key}.title`)}
        className="max-w-[46rem]"
        bodyClassName="flex flex-col gap-3"
      >
        <p className="text-sm">{t(`${key}.text`)}</p>
        <p className="text-sm text-muted-foreground">
          {t("notCounted")} {detail && t(`${key}.report`)}
        </p>
        {detail && (
          <div className="flex flex-col gap-1 border-t border-line-soft pt-3">
            <p className="text-xs text-muted-foreground">{t("detail")}</p>
            <p translate="no" className="font-mono text-xs break-words">
              {detail}
            </p>
          </div>
        )}
      </Panel>
    );
  }
  const at = STEPS.indexOf(match.status as (typeof STEPS)[number]);
  return (
    <Panel
      title={t("analysing.title")}
      className="max-w-[46rem]"
      bodyClassName="grid gap-x-8 gap-y-4 sm:grid-cols-2"
    >
      <div className="flex flex-col gap-2">
        <h3 className="text-xs text-muted-foreground">{t("analysing.steps")}</h3>
        <ol className="flex flex-col gap-1.5 text-sm">
          {STEPS.map((step, i) => {
            const done = i < at;
            const current = i === at;
            return (
              <li
                key={step}
                aria-current={current ? "step" : undefined}
                className={cn(
                  "flex items-center gap-2.5",
                  !done && !current && "text-muted-foreground",
                  current && "font-semibold",
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    "grid size-4 shrink-0 place-items-center rounded-full border",
                    done && "border-foreground bg-foreground text-background",
                    current && "border-foreground",
                    !done && !current && "border-border",
                  )}
                >
                  {done && <Check className="size-3" strokeWidth={3} />}
                  {current && (
                    <span className="size-1.5 rounded-full bg-foreground motion-safe:animate-pulse" />
                  )}
                </span>
                {t(`analysing.step.${step}`)}
                <span className="sr-only">
                  {done ? t("analysing.done") : current ? t("analysing.now") : ""}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
      <div className="flex flex-col gap-2">
        <h3 className="text-xs text-muted-foreground">{t("analysing.coming")}</h3>
        <ul className="flex list-disc flex-col gap-1 pl-4 text-sm marker:text-muted-foreground">
          {COMING.map((part) => (
            <li key={part}>{t(`analysing.parts.${part}`)}</li>
          ))}
        </ul>
      </div>
      <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-t border-line-soft pt-3 text-xs text-muted-foreground sm:col-span-2">
        {t("analysing.later")}
        {/* A plain link: a full load asks the API again, where the router could keep its copy. */}
        <a
          href={`/matches/${encodeURIComponent(match.id)}`}
          className="text-link underline underline-offset-3"
        >
          {t("analysing.reload")}
        </a>
      </p>
    </Panel>
  );
}
