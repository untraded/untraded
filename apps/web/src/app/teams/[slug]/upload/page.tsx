// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import { TeamHeader } from "@/components/teams/team-header";
import { Panel } from "@/components/ui/panel";
import { RefreshWhile } from "@/components/upload/refresh-while";
import { UploadForm } from "@/components/upload/upload-form";
import { UploadRow } from "@/components/upload/upload-row";
import type { Locale } from "@/i18n/locale";
import { getMe, getTeam, getTeamUploads } from "@/lib/api";
import { bytes } from "@/lib/format";
import { allows, teamHref, validTeamParam } from "@/lib/teams";
import type { SendError } from "@/lib/upload";

type Params = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  if (!validTeamParam(slug)) return {};
  const [team, t] = await Promise.all([getTeam(slug), getTranslations("teamUpload")]);
  return team ? { title: `${t("title")} · ${team.name}` } : {};
}

/** The errors a send for a team can meet, the player's plus the team's own. */
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
  "forbidden",
  "not_enough_roster",
  "team_not_found",
] as const satisfies readonly SendError[];
/** The messages that differ for a team: its limits, its roster, the member's role. */
const TEAM_ERRORS = new Set<string>([
  "quota",
  "busy",
  "forbidden",
  "not_enough_roster",
  "team_not_found",
]);

/**
 * Sending a match for the team (E4): a scrim, or an official FACEIT or ESEA match, which counts
 * for the team alone. Members who may send (`matches.upload`) get the form; every member who reads
 * the team's matches gets the history, with who sent each demo. Why a demo would be refused is
 * said before sending, the roster rule above all: 3 players of the roster on one side.
 */
export default async function TeamUploadPage({ params }: Params) {
  const { slug } = await params;
  if (!validTeamParam(slug)) notFound();
  const me = await getMe();
  if (!me) redirect("/");
  const team = await getTeam(slug);
  if (!team) redirect("/");
  // The history needs `matches.read` (the API answers 403 without it): a role made without it
  // finds no page here, as the rail shows it no link.
  if (!allows(team.my_role.permissions, "matches.read")) notFound();
  const list = await getTeamUploads(slug);
  if (!list) redirect("/");
  const [t, solo] = await Promise.all([getTranslations("teamUpload"), getTranslations("upload")]);
  const locale = (await getLocale()) as Locale;
  const max = bytes(list.max_bytes, locale);
  const refusal = me.demo ? null : list.refusal;
  const processing = list.items.some((item) => item.state === "processing");
  const matchHref = (id: string) => `${teamHref(team.slug)}/matches/${encodeURIComponent(id)}`;
  const message = (key: (typeof SEND_ERRORS)[number]) =>
    TEAM_ERRORS.has(key)
      ? t(`errors.${key}`)
      : key === "too_large"
        ? solo("errors.too_large", { max })
        : solo(`errors.${key}`);
  // A refusal the team owns (its roster, its limits, the member's role), else the player's.
  const refusalText = (key: string, part: "title" | "text") =>
    t.has(`refusals.${key}.${part}`)
      ? t(`refusals.${key}.${part}`)
      : solo(`refusals.${key}.${part}`);

  return (
    <>
      <TeamHeader team={team} current="upload" />
      <section className="flex max-w-3xl flex-col gap-3.5">
        <header className="mb-2 flex flex-col gap-1.5">
          <h2 className="text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h2>
          <p className="max-w-prose text-sm text-muted-foreground">{t("lead")}</p>
        </header>

        {refusal && refusal !== "forbidden" && (
          // Said before the form, which it disables: a status, so it is read when the page opens.
          <div role="status">
            <Panel title={refusalText(refusal, "title")} className="border-l-[3px] border-l-loss">
              <p className="text-sm text-muted-foreground">
                {refusalText(refusal, "text")}{" "}
                {refusal === "consent" && (
                  <Link href="/settings" className="text-link underline underline-offset-3">
                    {solo("openSettings")}
                  </Link>
                )}
                {refusal === "not_enough_roster" && (
                  <Link
                    href={teamHref(team.slug, "members")}
                    className="text-link underline underline-offset-3"
                  >
                    {t("openRoster")}
                  </Link>
                )}
              </p>
            </Panel>
          </div>
        )}

        {refusal === "forbidden" ? (
          // A role that may not send reads the history only: no form to try.
          <p className="max-w-prose text-sm text-muted-foreground">{t("readOnly")}</p>
        ) : (
          <Panel title={solo("file")} aside={t("rule")}>
            <UploadForm
              team={team.slug}
              maxBytes={list.max_bytes}
              disabled={me.demo || refusal !== null}
              locale={locale}
              labels={{
                dropTitle: solo("dropTitle"),
                dropHint: solo("dropHint", { max }),
                choose: solo("choose"),
                remove: solo("remove"),
                file: solo("file"),
                mode: solo("mode"),
                modes: {
                  faceit: solo("modes.faceit"),
                  esea: solo("modes.esea"),
                  scrim: solo("modes.scrim"),
                },
                date: solo("date"),
                dateHint: t("dateHint"),
                dateFaceit: t("dateFaceit"),
                send: solo("send"),
                cancel: solo("cancel"),
                progress: solo.raw("progress") as string,
                done: t("done"),
                aborted: solo("aborted"),
                errors: {
                  ...Object.fromEntries(SEND_ERRORS.map((key) => [key, message(key)])),
                  unknown: message("unknown"),
                },
              }}
            />
          </Panel>
        )}

        <Panel title={t("history")} aside={solo("historyHint")} flush>
          {list.items.length === 0 ? (
            <p className="px-3.5 py-3 text-sm text-muted-foreground">{t("empty")}</p>
          ) : (
            <ul>
              {list.items.map((item) => (
                <UploadRow
                  key={item.upload_id}
                  item={item}
                  matchHref={matchHref(item.match_id)}
                  team
                />
              ))}
            </ul>
          )}
        </Panel>
        <RefreshWhile active={processing} />
      </section>
    </>
  );
}
