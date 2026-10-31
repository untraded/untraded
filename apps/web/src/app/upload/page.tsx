// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { RefreshWhile } from "@/components/upload/refresh-while";
import { UploadForm } from "@/components/upload/upload-form";
import type { Locale } from "@/i18n/locale";
import { getMe, getUploads, type UploadLine } from "@/lib/api";
import { cn } from "@/lib/cn";
import { bytes, dateTime, mapName } from "@/lib/format";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("upload"))("title") };
}

const SEND_ERRORS = [
  "not_a_demo",
  "too_large",
  "consent",
  "quota",
  "busy",
  "disk_full",
  "off",
  "date",
  "network",
  "unknown",
] as const;

/**
 * Sending a demo (FACEIT, ESEA, a scrim, or a Premier match the bot missed): why it would be
 * refused, said before sending; the form; then what became of each demo sent in the last 30 days,
 * refreshed while one is being analysed.
 */
export default async function UploadPage() {
  const [list, me] = await Promise.all([getUploads(), getMe()]);
  if (!list) redirect("/");
  if (me?.demo) {
    const t = await getTranslations("upload");
    const demo = await getTranslations("demo");
    return (
      <section className="flex max-w-3xl flex-col gap-5">
        <h1 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
        <p className="rounded-md border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
          {demo("upload")}
        </p>
      </section>
    );
  }
  const t = await getTranslations("upload");
  const locale = (await getLocale()) as Locale;
  const max = bytes(list.max_bytes, locale, 1024);
  const refusal = list.refusal;
  const processing = list.items.some((item) => item.state === "processing");

  return (
    <section className="flex max-w-3xl flex-col gap-5">
      <header className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
        <p className="max-w-prose text-sm text-muted-foreground">{t("lead")}</p>
      </header>

      {refusal && (
        <div
          role="status"
          className="rounded-md border border-border border-l-[3px] border-l-loss bg-card px-3.5 py-2.5 text-sm"
        >
          <p className="font-semibold">{t(`refusals.${refusal}.title`)}</p>
          <p className="text-muted-foreground">
            {t(`refusals.${refusal}.text`)}{" "}
            {refusal === "consent" && (
              <Link href="/settings" className="text-link underline underline-offset-3">
                {t("openSettings")}
              </Link>
            )}
          </p>
        </div>
      )}

      <UploadForm
        maxBytes={list.max_bytes}
        disabled={refusal !== null}
        locale={locale}
        labels={{
          dropTitle: t("dropTitle"),
          dropHint: t("dropHint", { max }),
          choose: t("choose"),
          remove: t("remove"),
          file: t("file"),
          mode: t("mode"),
          modes: { faceit: t("modes.faceit"), esea: t("modes.esea"), scrim: t("modes.scrim") },
          date: t("date"),
          dateHint: t("dateHint"),
          dateFaceit: t("dateFaceit"),
          send: t("send"),
          cancel: t("cancel"),
          progress: t.raw("progress") as string,
          done: t("done"),
          aborted: t("aborted"),
          errors: Object.fromEntries(
            SEND_ERRORS.map((key) => [
              key,
              key === "too_large" ? t("errors.too_large", { max }) : t(`errors.${key}`),
            ]),
          ) as Record<(typeof SEND_ERRORS)[number], string>,
        }}
      />

      <section aria-labelledby="uploads" className="flex flex-col gap-2">
        <h2
          id="uploads"
          className="flex flex-wrap items-baseline justify-between gap-x-3 text-sm font-semibold text-muted-foreground"
        >
          {t("history")} <span className="font-normal">{t("historyHint")}</span>
        </h2>
        {list.items.length === 0 ? (
          <p className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
            {t("empty")}
          </p>
        ) : (
          <ul className="rounded-lg border border-border bg-card">
            {list.items.map((item) => (
              <UploadRow key={item.upload_id} item={item} />
            ))}
          </ul>
        )}
      </section>
      <RefreshWhile active={processing} />
    </section>
  );
}

async function UploadRow({ item }: { item: UploadLine }) {
  const t = await getTranslations("upload");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const mode = t.has(`modes.${item.mode}`) ? t(`modes.${item.mode}`) : item.mode;
  const reason =
    item.reason && t.has(`reasons.${item.reason}`) ? t(`reasons.${item.reason}`) : null;
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 border-t border-line-soft px-4 py-3 first:border-t-0">
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
          {t("received", { date: dateTime(item.received_at, locale, timeZone) })}
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
          <Link
            href={`/matches/${item.match_id}`}
            className="text-link underline underline-offset-3"
          >
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
