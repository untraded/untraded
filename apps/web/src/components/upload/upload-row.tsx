// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import type { Locale } from "@/i18n/locale";
import type { UploadLine } from "@/lib/api";
import { cn } from "@/lib/cn";
import { dateTime, mapName } from "@/lib/format";

/**
 * One demo sent, in an upload history (the player's or a team's): its map and mode, when it was
 * played and sent (and by whom, in a team's history: `team`), and what became of it, with a link
 * to the match once it is ready (`matchHref`).
 */
export async function UploadRow({
  item,
  matchHref,
  team = false,
}: {
  item: UploadLine;
  matchHref: string;
  /** A team's history: the sender is named, "a former member" once their account is erased. */
  team?: boolean;
}) {
  const t = await getTranslations("upload");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const mode = t.has(`modes.${item.mode}`) ? t(`modes.${item.mode}`) : item.mode;
  const reason =
    item.reason && t.has(`reasons.${item.reason}`) ? t(`reasons.${item.reason}`) : null;
  const received = dateTime(item.received_at, locale, timeZone);
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 border-t border-line-soft px-3.5 py-2.5 first:border-t-0">
      <div className="min-w-0">
        <p className="font-semibold">
          {item.map ? (
            mapName(item.map)
          ) : (
            <span className="font-normal text-muted-foreground">{t("mapUnknown")}</span>
          )}
          <span className="font-normal text-muted-foreground"> · {mode}</span>
        </p>
        <p className="text-xs text-muted-foreground tabular-nums">
          {item.played_at && `${dateTime(item.played_at, locale, timeZone)} · `}
          {!team
            ? t("received", { date: received })
            : item.sent_by
              ? t("receivedBy", { date: received, name: item.sent_by })
              : t("receivedFormer", { date: received })}
        </p>
      </div>
      <p
        className={cn(
          "self-center text-right text-[0.8125rem]",
          item.state === "processing" && "text-muted-foreground",
          (item.state === "refused" || item.state === "failed") && "font-semibold",
        )}
      >
        {item.state === "ready" ? (
          <Link href={matchHref} className="text-link underline underline-offset-3">
            {t("openMatch")}
          </Link>
        ) : (
          t(`states.${item.state}`)
        )}
      </p>
      {reason && <p className="col-span-2 text-[0.8125rem] text-muted-foreground">{reason}</p>}
    </li>
  );
}
