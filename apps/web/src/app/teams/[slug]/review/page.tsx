// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ArrowDown, ArrowUp, MessageSquare, OctagonX, Play } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import {
  createPlaylist,
  deletePlaylist,
  movePlaylistRound,
  removePlaylistRound,
  updatePlaylist,
} from "@/app/teams/review-actions";
import { ConfirmSubmit } from "@/components/confirm-submit";
import { HiddenFields } from "@/components/hidden-fields";
import { Button, buttonVariants } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type { Locale } from "@/i18n/locale";
import {
  findPlaylist,
  getMe,
  getPlaylists,
  getTeam,
  type Playlist,
  type PlaylistRound,
} from "@/lib/api";
import { cn } from "@/lib/cn";
import { mapName, shortDay } from "@/lib/format";
import {
  PLAYLIST_DESCRIPTION_MAX,
  PLAYLIST_NAME_MAX,
  reviewHref,
  reviewRoundHref,
  shownError,
  viewerHref,
} from "@/lib/review";
import { readsMatches, validTeamParam } from "@/lib/teams";

type Params = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ playlist?: string; error?: string }>;
};

type T = (key: string, values?: Record<string, string | number>) => string;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const FIELD = "w-full rounded-md border border-input bg-card px-3 text-sm";

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  if (!validTeamParam(slug)) return {};
  const [team, t] = await Promise.all([getTeam(slug), getTranslations("teamReview")]);
  return team ? { title: `${t("pageTitle")} · ${team.name}` } : {};
}

/**
 * A team's review: its playlists of rounds on the left (or first, on a phone), the one chosen on
 * the right with its rounds in order, each with a link to the 2D viewer and to its review on the
 * match page. Members who manage the review create, rename, order and delete them; the others read.
 * Names, descriptions and tags are players' text, shown as text.
 */
export default async function TeamReviewPage({ params, searchParams }: Params) {
  const { slug } = await params;
  if (!validTeamParam(slug)) notFound();
  const [me, query] = await Promise.all([getMe(), searchParams]);
  if (!me) redirect("/");
  const team = await getTeam(slug);
  if (!team) redirect("/");
  if (!readsMatches(team.my_role.permissions)) notFound();
  const [playlists, t, locale, timeZone] = await Promise.all([
    getPlaylists(team.slug),
    getTranslations("teamReview"),
    getLocale(),
    getTimeZone(),
  ]);
  const list = playlists ?? [];
  const wanted = query.playlist && UUID.test(query.playlist) ? query.playlist.toLowerCase() : null;
  const chosen = list.find((p) => p.id === wanted) ?? list[0] ?? null;
  const playlist = chosen ? await findPlaylist(team.slug, chosen.id) : null;
  const error = shownError(query.error);
  const manage =
    me.demo !== true && (playlist?.permissions.manage ?? manages(team.my_role.permissions));
  return (
    <>
      <h1 className="mb-5 text-2xl font-semibold break-words md:text-[1.75rem]">{t("title")}</h1>
      <div className="flex flex-col gap-4">
        {error && (
          <p
            id="notice"
            role="alert"
            className="flex items-start gap-2 rounded-lg border border-destructive/40 px-3.5 py-2.5 text-sm text-destructive"
          >
            <OctagonX aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            {t(`errors.${error}`)}
          </p>
        )}
        <p className="text-sm text-muted-foreground">{t("pageLead")}</p>
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
          <Panel
            title={t("playlists")}
            aside={
              <span className="tabular-nums">{t("playlistsCount", { count: list.length })}</span>
            }
            flush
          >
            {list.length === 0 ? (
              <p className="px-3.5 py-3 text-sm text-muted-foreground">
                {manage ? t("noPlaylistManage") : t("noPlaylistRead")}
              </p>
            ) : (
              <ul className="py-1">
                {list.map((p) => (
                  <li key={p.id}>
                    <Link
                      href={reviewHref(team.slug, p.id)}
                      aria-current={p.id === chosen?.id ? "page" : undefined}
                      className="flex items-baseline justify-between gap-3 px-3.5 py-2 text-sm hover:bg-muted aria-[current=page]:bg-highlight-soft aria-[current=page]:font-semibold aria-[current=page]:shadow-[inset_2px_0_0_var(--highlight)]"
                    >
                      <span className="min-w-0 break-words">{p.name}</span>
                      <span className="shrink-0 text-xs font-normal text-muted-foreground tabular-nums">
                        {t("roundsCount", { count: p.rounds })}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            {manage && (
              <form
                action={createPlaylist}
                className="flex flex-col gap-2 border-t border-line-soft px-3.5 py-3"
              >
                <input type="hidden" name="slug" value={team.slug} />
                <label htmlFor="new-playlist" className="text-xs font-medium">
                  {t("newPlaylist")}
                </label>
                <input
                  id="new-playlist"
                  name="name"
                  required
                  maxLength={PLAYLIST_NAME_MAX}
                  placeholder={t("namePlaceholder")}
                  className={cn(FIELD, "h-8")}
                />
                <label htmlFor="new-description" className="sr-only">
                  {t("description")}
                </label>
                <input
                  id="new-description"
                  name="description"
                  maxLength={PLAYLIST_DESCRIPTION_MAX}
                  placeholder={t("descriptionPlaceholder")}
                  className={cn(FIELD, "h-8")}
                />
                <Button type="submit" size="sm" className="self-start">
                  {t("create")}
                </Button>
              </form>
            )}
          </Panel>

          {chosen &&
            (playlist ? (
              <PlaylistPanel
                slug={team.slug}
                playlist={playlist}
                manage={manage}
                locale={locale as Locale}
                timeZone={timeZone}
                t={t}
              />
            ) : (
              <Panel title={chosen.name}>
                <p className="text-sm text-muted-foreground">{t("playlistUnavailable")}</p>
              </Panel>
            ))}
        </div>
      </div>
    </>
  );
}

function manages(permissions: readonly string[]): boolean {
  return permissions.includes("*") || permissions.includes("review.manage");
}

function PlaylistPanel({
  slug,
  playlist,
  manage,
  locale,
  timeZone,
  t,
}: {
  slug: string;
  playlist: Playlist;
  manage: boolean;
  locale: Locale;
  timeZone: string;
  t: T;
}) {
  const ids = { slug, playlist: playlist.id };
  return (
    <Panel
      title={<span className="break-words">{playlist.name}</span>}
      aside={
        <span className="tabular-nums">{t("roundsCount", { count: playlist.items.length })}</span>
      }
      flush
    >
      {(playlist.description || manage) && (
        <div className="flex flex-col gap-2 border-b border-line-soft px-3.5 py-2.5">
          {playlist.description && (
            <p className="text-sm break-words text-muted-foreground">{playlist.description}</p>
          )}
          {manage && (
            <div className="flex flex-wrap items-start gap-2">
              <details className="open:w-full">
                <summary
                  className={cn(
                    buttonVariants({ variant: "outline", size: "sm" }),
                    "cursor-pointer list-none [&::-webkit-details-marker]:hidden",
                  )}
                >
                  {t("editPlaylist")}
                </summary>
                <form action={updatePlaylist} className="mt-1.5 flex flex-col gap-2 sm:w-[28rem]">
                  <HiddenFields values={ids} />
                  <label htmlFor="playlist-name" className="text-xs font-medium">
                    {t("name")}
                  </label>
                  <input
                    id="playlist-name"
                    name="name"
                    required
                    maxLength={PLAYLIST_NAME_MAX}
                    defaultValue={playlist.name}
                    className={cn(FIELD, "h-8")}
                  />
                  <label htmlFor="playlist-description" className="text-xs font-medium">
                    {t("description")}
                  </label>
                  <input
                    id="playlist-description"
                    name="description"
                    maxLength={PLAYLIST_DESCRIPTION_MAX}
                    defaultValue={playlist.description}
                    className={cn(FIELD, "h-8")}
                  />
                  <Button type="submit" size="sm" className="self-start">
                    {t("save")}
                  </Button>
                </form>
              </details>
              <form action={deletePlaylist}>
                <HiddenFields values={ids} />
                <ConfirmSubmit
                  label={t("deletePlaylist")}
                  question={t("deletePlaylistQuestion")}
                  confirm={t("deleteConfirm")}
                  cancel={t("cancel")}
                  size="sm"
                />
              </form>
            </div>
          )}
        </div>
      )}
      {playlist.items.length === 0 ? (
        <p className="px-3.5 py-3 text-sm text-muted-foreground">
          {manage ? t("emptyManage") : t("emptyRead")}
        </p>
      ) : (
        <ol>
          {playlist.items.map((item, index) => (
            <PlaylistItem
              key={`${item.match_id}-${item.round}`}
              item={item}
              index={index}
              last={index === playlist.items.length - 1}
              ids={ids}
              manage={manage}
              locale={locale}
              timeZone={timeZone}
              t={t}
            />
          ))}
        </ol>
      )}
    </Panel>
  );
}

function PlaylistItem({
  item,
  index,
  last,
  ids,
  manage,
  locale,
  timeZone,
  t,
}: {
  item: PlaylistRound;
  index: number;
  last: boolean;
  ids: { slug: string; playlist: string };
  manage: boolean;
  locale: Locale;
  timeZone: string;
  t: T;
}) {
  const won = item.our_team && item.winner_team ? item.winner_team === item.our_team : null;
  const where = [
    mapName(item.map),
    item.played_at ? shortDay(item.played_at, locale, timeZone) : null,
  ]
    .filter(Boolean)
    .join(" · ");
  const name = t("itemName", { round: item.round, where });
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-line-soft px-3.5 py-2 last:border-b-0">
      <span className="w-6 shrink-0 text-xs text-muted-foreground tabular-nums">{index + 1}</span>
      <span className="min-w-36 flex-1">
        <span className="block text-sm font-medium whitespace-nowrap">
          {t("round", { round: item.round })}
          {won !== null && (
            <span className={cn("ml-2 text-xs font-normal", won ? "text-win" : "text-loss")}>
              {t(won ? "wonShort" : "lostShort")}
            </span>
          )}
        </span>
        <span className="block text-xs text-muted-foreground">{where}</span>
      </span>
      {item.tags.length > 0 && (
        <span className="flex min-w-0 flex-wrap gap-1">
          {item.tags.map((tag) => (
            <span
              key={tag}
              title={tag}
              className="max-w-full truncate rounded-sm border border-border px-1.5 py-px text-[0.6875rem]"
            >
              {tag}
            </span>
          ))}
        </span>
      )}
      <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.8125rem]">
        {item.comments > 0 && (
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground tabular-nums">
            <MessageSquare aria-hidden="true" className="size-3.5" />
            {t("comments", { count: item.comments })}
          </span>
        )}
        <Link
          href={viewerHref(item.match_id, item.round)}
          aria-label={t("viewerOf", { name })}
          className="inline-flex items-center gap-1 text-link underline underline-offset-3"
        >
          <Play aria-hidden="true" className="size-3.5" />
          {t("viewerShort")}
        </Link>
        <Link
          href={reviewRoundHref(ids.slug, item.match_id, item.round)}
          aria-label={t("reviewOf", { name })}
          className="text-link underline underline-offset-3"
        >
          {t("reviewShort")}
        </Link>
      </span>
      {manage && (
        <span className="flex items-center gap-1">
          <form action={movePlaylistRound}>
            <HiddenFields values={{ ...ids, match: item.match_id, round: item.round, by: "up" }} />
            <Button
              type="submit"
              size="icon-sm"
              variant="ghost"
              disabled={index === 0}
              aria-label={t("moveUp", { name })}
            >
              <ArrowUp aria-hidden="true" />
            </Button>
          </form>
          <form action={movePlaylistRound}>
            <HiddenFields
              values={{ ...ids, match: item.match_id, round: item.round, by: "down" }}
            />
            <Button
              type="submit"
              size="icon-sm"
              variant="ghost"
              disabled={last}
              aria-label={t("moveDown", { name })}
            >
              <ArrowDown aria-hidden="true" />
            </Button>
          </form>
          <form action={removePlaylistRound}>
            <HiddenFields values={{ ...ids, match: item.match_id, round: item.round }} />
            <Button type="submit" size="sm" variant="ghost" aria-label={t("removeOf", { name })}>
              {t("remove")}
            </Button>
          </form>
        </span>
      )}
    </li>
  );
}
