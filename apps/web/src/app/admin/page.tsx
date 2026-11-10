// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

import { CircleCheck, OctagonX, TriangleAlert } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import {
  changeSource,
  dismissRequest,
  erasePlayer,
  inviteRequest,
  revokeInvitation,
} from "@/app/admin/actions";
import { AdminHeader } from "@/components/admin/admin-header";
import { InviteForm } from "@/components/admin/invite-form";
import { ConfirmSubmit } from "@/components/confirm-submit";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type { Locale } from "@/i18n/locale";
import { adminOnlyMetadata } from "@/lib/admin-metadata";
import {
  type AdminPlayer,
  getAdminPlayers,
  getInvitationRequests,
  getMe,
  type InvitationRequest,
} from "@/lib/api";
import { cn } from "@/lib/cn";
import { dateTime, day } from "@/lib/format";

export async function generateMetadata(): Promise<Metadata> {
  return adminOnlyMetadata(async () => (await getTranslations("admin"))("players"));
}

const ERASE_NOTES = {
  missing: "eraseMissing",
  self: "eraseSelf",
  failed: "eraseFailed",
} as const;

const REQUEST_NOTES = {
  name: "requestName",
  exists: "requestExists",
  failed: "requestFailed",
} as const;

/**
 * Every player, from invited to followed, and what the admin can do about each: invite, answer
 * the requests, pause or remove a source, erase. A player who is not an admin gets the 404: the
 * page does not say it exists.
 */
export default async function AdminPlayers({
  searchParams,
}: {
  searchParams: Promise<{ erased?: string; erase?: string; request?: string }>;
}) {
  const me = await getMe();
  if (!me) redirect("/");
  if (!me.admin) notFound();
  const [playerList, requestList, t] = await Promise.all([
    getAdminPlayers(),
    getInvitationRequests(),
    getTranslations("admin"),
  ]);
  const players = playerList?.items ?? [];
  const requests = requestList?.items ?? [];
  const { erased, erase, request } = await searchParams;
  const requestNote =
    request && request in REQUEST_NOTES
      ? REQUEST_NOTES[request as keyof typeof REQUEST_NOTES]
      : null;
  const refused =
    erase && erase in ERASE_NOTES ? ERASE_NOTES[erase as keyof typeof ERASE_NOTES] : null;
  return (
    <>
      <AdminHeader current="players">
        <span className="tabular-nums">{t("playersCount", { count: players.length })}</span>
        {requests.length > 0 && (
          <a
            href="#requests"
            className="tabular-nums underline decoration-muted-foreground underline-offset-3 hover:decoration-foreground"
          >
            {t("requestsCount", { count: requests.length })}
          </a>
        )}
      </AdminHeader>
      <div className="flex flex-col gap-4">
        {(erased || refused) && (
          <p
            role={refused ? "alert" : "status"}
            className={cn(
              "flex items-start gap-2 rounded-lg border px-3.5 py-2.5 text-sm",
              refused ? "border-destructive/40 text-destructive" : "border-border bg-card",
            )}
          >
            {refused ? (
              <OctagonX aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            ) : (
              <CircleCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-win" />
            )}
            {refused ? t(refused) : t("erased")}
          </p>
        )}
        <Panel title={t("inviteTitle")}>
          <InviteForm
            labels={{
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
        </Panel>
        {requests.length > 0 && <Requests requests={requests} note={requestNote} />}
        <Panel
          title={t("players")}
          aside={
            <span className="tabular-nums">{t("playersCount", { count: players.length })}</span>
          }
          flush
        >
          {players.length === 0 ? (
            <p className="px-3.5 py-3 text-sm text-muted-foreground">{t("empty")}</p>
          ) : (
            <>
              <div
                aria-hidden="true"
                className="hidden grid-cols-[minmax(0,1.3fr)_7rem_minmax(0,1fr)_minmax(0,1.2fr)_5rem_minmax(0,1.4fr)] gap-4 border-b border-line-soft px-3.5 py-1.5 text-xs font-medium text-muted-foreground lg:grid"
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
            </>
          )}
        </Panel>
      </div>
    </>
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
    <li className="grid gap-x-4 gap-y-2 border-t border-line-soft px-3.5 py-3 text-sm first:border-t-0 sm:grid-cols-2 lg:grid-cols-[minmax(0,1.3fr)_7rem_minmax(0,1fr)_minmax(0,1.2fr)_5rem_minmax(0,1.4fr)] lg:items-start">
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
          <span className="mt-0.5 flex items-start gap-1 text-destructive">
            <TriangleAlert aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
            <span className="sr-only">{t("collectError")} </span>
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

/** The Steam accounts that asked for an invitation: invite each under a name, or dismiss it. */
async function Requests({
  requests,
  note,
}: {
  requests: InvitationRequest[];
  note: (typeof REQUEST_NOTES)[keyof typeof REQUEST_NOTES] | null;
}) {
  const t = await getTranslations("admin");
  const locale = (await getLocale()) as Locale;
  const timeZone = await getTimeZone();
  const input = "h-8 w-40 rounded-md border border-input bg-card px-2 text-sm";
  return (
    <Panel
      title={<span id="requests">{t("requestsTitle")}</span>}
      aside={<span className="tabular-nums">{t("requestsCount", { count: requests.length })}</span>}
      flush
    >
      <p className="border-b border-line-soft px-3.5 py-2 text-xs text-muted-foreground">
        {t("requestsLead")}
      </p>
      {note && (
        <p
          role="alert"
          className="flex items-start gap-2 border-b border-line-soft px-3.5 py-2 text-sm text-destructive"
        >
          <OctagonX aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {t(note)}
        </p>
      )}
      <ul className="flex flex-col">
        {requests.map((r) => (
          <li
            key={r.steam_id}
            className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line-soft px-3.5 py-2.5 first:border-t-0"
          >
            <div className="min-w-0 flex-1 max-sm:basis-full">
              <p className="truncate font-semibold">{r.persona_name ?? r.steam_id}</p>
              <p className="text-xs text-muted-foreground">
                <span className="font-mono" translate="no">
                  {r.steam_id}
                </span>{" "}
                ·{" "}
                <a
                  href={`https://steamcommunity.com/profiles/${r.steam_id}`}
                  rel="noopener noreferrer"
                  target="_blank"
                  className="underline underline-offset-2 hover:text-foreground"
                >
                  {t("steamProfile")}
                </a>{" "}
                · {t("requestedOn", { date: dateTime(r.requested_at, locale, timeZone) })}
              </p>
            </div>
            <form action={inviteRequest} className="flex items-center gap-2">
              <input type="hidden" name="steam_id" value={r.steam_id} />
              <input
                name="display_name"
                required
                maxLength={64}
                autoComplete="off"
                defaultValue={r.persona_name ?? ""}
                aria-label={t("displayName")}
                className={input}
              />
              <Button type="submit" size="sm">
                {t("invite")}
              </Button>
            </form>
            <form action={dismissRequest}>
              <input type="hidden" name="steam_id" value={r.steam_id} />
              <Button type="submit" variant="outline" size="sm">
                {t("dismiss")}
              </Button>
            </form>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
