// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import { changeSource, erasePlayer, revokeInvitation } from "@/app/admin/actions";
import { AdminHeader } from "@/components/admin/admin-header";
import { InviteForm } from "@/components/admin/invite-form";
import { ConfirmSubmit } from "@/components/confirm-submit";
import { Button } from "@/components/ui/button";
import type { Locale } from "@/i18n/locale";
import { type AdminPlayer, getAdminPlayers, getMe } from "@/lib/api";
import { cn } from "@/lib/cn";
import { dateTime, day } from "@/lib/format";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("admin"))("players") };
}

/** Every player, from invited to followed, and what the admin can do about each. */
const ERASE_NOTES = {
  missing: "eraseMissing",
  self: "eraseSelf",
  failed: "eraseFailed",
} as const;

export default async function AdminPlayers({
  searchParams,
}: {
  searchParams: Promise<{ erased?: string; erase?: string }>;
}) {
  const me = await getMe();
  if (!me) redirect("/");
  const t = await getTranslations("admin");
  if (!me.admin) {
    return <p className="text-muted-foreground">{t("forbidden")}</p>;
  }
  const players = (await getAdminPlayers())?.items ?? [];
  const { erased, erase } = await searchParams;
  const refused =
    erase && erase in ERASE_NOTES ? ERASE_NOTES[erase as keyof typeof ERASE_NOTES] : null;
  return (
    <section className="flex flex-col gap-5">
      <AdminHeader current="players" />
      <InviteForm
        labels={{
          title: t("inviteTitle"),
          steamId: t("steamId"),
          steamIdHelp: t("steamIdHelp"),
          displayName: t("displayName"),
          submit: t("invite"),
          invited: t("invited", { name: "{name}" }),
          errors: {
            steam_id: t("errorSteamId"),
            display_name: t("errorDisplayName"),
            exists: t("errorExists"),
            failed: t("errorFailed"),
          },
        }}
      />
      {(erased || refused) && (
        <p
          role={refused ? "alert" : "status"}
          className={cn(
            "rounded-md border px-4 py-2.5 text-sm",
            refused ? "border-destructive/40 text-destructive" : "border-border bg-card",
          )}
        >
          {refused ? t(refused) : t("erased")}
        </p>
      )}
      {players.length === 0 ? (
        <p className="text-muted-foreground">{t("empty")}</p>
      ) : (
        <div className="rounded-lg border border-border bg-card">
          <div
            aria-hidden="true"
            className="hidden grid-cols-[minmax(0,1.3fr)_7rem_minmax(0,1fr)_minmax(0,1.2fr)_5rem_minmax(0,1.4fr)] gap-4 border-b border-border px-4 py-2 text-xs text-muted-foreground lg:grid"
          >
            <span>{t("player")}</span>
            <span>{t("state")}</span>
            <span>{t("consent")}</span>
            <span>{t("lastCollect")}</span>
            <span className="text-right">{t("matchesCol")}</span>
            <span>{t("actions")}</span>
          </div>
          <ul>
            {players.map((player) => (
              <PlayerRow
                key={player.steam_id}
                player={player}
                self={player.steam_id === me.steam_id}
              />
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

async function PlayerRow({ player, self }: { player: AdminPlayer; self: boolean }) {
  const t = await getTranslations("admin");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const { consent, source } = player;
  const error = source?.last_error;
  // Labels shown on phones only, where there is no column header.
  const caption = "text-xs text-muted-foreground lg:hidden";
  return (
    <li className="grid gap-x-4 gap-y-2 border-t border-line-soft px-4 py-3 text-sm first:border-t-0 sm:grid-cols-2 lg:grid-cols-[minmax(0,1.3fr)_7rem_minmax(0,1fr)_minmax(0,1.2fr)_5rem_minmax(0,1.4fr)] lg:items-start">
      <div className="min-w-0">
        <p className="truncate font-semibold">{player.display_name}</p>
        <p className="font-mono text-xs text-muted-foreground" translate="no">
          {player.steam_id}
        </p>
      </div>
      <div>
        <span className={caption}>{t("state")} </span>
        <span
          className={cn(
            "inline-block rounded-sm bg-muted px-1.5 py-0.5 text-xs font-medium",
            (player.state === "withdrawn" || player.state === "paused") && "text-muted-foreground",
          )}
        >
          {t(`states.${player.state}`)}
        </span>
      </div>
      <div className="text-[0.8125rem]">
        <span className={caption}>{t("consent")} </span>
        {consent ? (
          <>
            {t("consentLine", {
              version: consent.text_version,
              date: day(consent.recorded_at.slice(0, 10), locale),
            })}
            <span className="block text-muted-foreground">
              {consent.research_corpus ? t("corpusYes") : t("corpusNo")}
            </span>
          </>
        ) : (
          t("none")
        )}
      </div>
      <div className="text-[0.8125rem]">
        <span className={caption}>{t("lastCollect")} </span>
        {source?.last_success_at ? dateTime(source.last_success_at, locale, timeZone) : t("none")}
        {error && (
          <span className="block text-destructive">
            {error === "403"
              ? t("error403")
              : error === "412"
                ? t("error412")
                : t("errorOther", { error })}
          </span>
        )}
      </div>
      <div className="text-[0.8125rem] lg:text-right">
        <span className={caption}>{t("matchesCol")} </span>
        <span className="font-semibold">{player.matches}</span>
        {player.last_match_at && (
          <span className="block text-muted-foreground">
            {t("lastMatch", { date: day(player.last_match_at.slice(0, 10), locale) })}
          </span>
        )}
      </div>
      <div className="flex flex-col items-start gap-2">
        <Actions player={player} />
        {self ? (
          <p className="text-xs text-muted-foreground">
            {t("you")} ·{" "}
            <Link href="/settings" className="underline underline-offset-2 hover:text-foreground">
              {t("yourSettings")}
            </Link>
          </p>
        ) : (
          <form action={erasePlayer}>
            <input type="hidden" name="steam_id" value={player.steam_id} />
            <ConfirmSubmit
              size="sm"
              label={t("erase")}
              question={t("eraseConfirm", { name: player.display_name })}
              confirm={t("eraseYes")}
              cancel={t("cancel")}
            />
          </form>
        )}
      </div>
    </li>
  );
}

async function Actions({ player }: { player: AdminPlayer }) {
  const t = await getTranslations("admin");
  const { source } = player;
  if (player.state === "invited") {
    return (
      <form action={revokeInvitation}>
        <input type="hidden" name="steam_id" value={player.steam_id} />
        <Button type="submit" variant="outline" size="sm">
          {t("revoke")}
        </Button>
      </form>
    );
  }
  if (!source) return null;
  return (
    <form action={changeSource} className="flex flex-wrap items-center gap-2">
      <input type="hidden" name="source" value={source.id} />
      {source.enabled ? (
        <Button type="submit" variant="outline" size="sm" name="intent" value="pause">
          {t("pause")}
        </Button>
      ) : (
        player.state !== "withdrawn" && (
          <Button type="submit" variant="outline" size="sm" name="intent" value="resume">
            {t("resume")}
          </Button>
        )
      )}
      <ConfirmSubmit
        size="sm"
        label={t("remove")}
        question={t("removeConfirm", { name: player.display_name })}
        confirm={t("confirm")}
        cancel={t("cancel")}
        name="intent"
        value="remove"
      />
    </form>
  );
}
