// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { apiSend, findPlaylist, refusalCode } from "@/lib/api";
import {
  COMMENT_MAX,
  moved,
  PLAYLIST_DESCRIPTION_MAX,
  PLAYLIST_NAME_MAX,
  parseTags,
  type ReviewError,
  reviewError,
  reviewHref,
  roundAnchor,
  TAG_MAX,
  TAGS_PER_ROUND,
} from "@/lib/review";
import { teamMatchHref } from "@/lib/teams";

// A team's review writes, as `docs/contrat-api-equipes-e7.md` (HQ) names them. Every id is checked
// here before it reaches an API path, and the texts are bounded as the API bounds them; the API
// checks the permissions and the limits again. A refusal comes back in the page's address as its
// code (`?error=comment_invalid`), never with anything else.

const SLUG = /^[a-z0-9-]{3,32}$/i;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function field(formData: FormData, name: string): string {
  return String(formData.get(name) ?? "");
}

function slugOf(formData: FormData): string | null {
  const slug = field(formData, "slug").trim();
  return SLUG.test(slug) ? slug.toLowerCase() : null;
}

function idOf(formData: FormData, name: string): string | null {
  const id = field(formData, name).trim();
  return UUID.test(id) ? id.toLowerCase() : null;
}

function roundOf(formData: FormData): number | null {
  const round = Number(field(formData, "round"));
  return Number.isInteger(round) && round >= 1 && round <= 99 ? round : null;
}

/** A match's round as the forms of the match page send it. */
function roundTarget(formData: FormData) {
  const slug = slugOf(formData);
  const match = idOf(formData, "match");
  const round = roundOf(formData);
  return slug && match && round ? { slug, match, round } : null;
}

/** Back to the round on the team's match page, its block open, with what went wrong if anything. */
function backToRound(
  target: { slug: string; match: string; round: number },
  error: ReviewError | null,
): never {
  const page = teamMatchHref(target.slug, target.match);
  revalidatePath(page);
  const query = `round=${target.round}${error ? `&error=${error}` : ""}`;
  redirect(`${page}?${query}#${roundAnchor(target.round)}`);
}

/** Back to the team's review page, on a playlist when given, with what went wrong if anything. */
function backToReview(slug: string, playlist: string | null, error: ReviewError | null): never {
  const page = reviewHref(slug, playlist ?? undefined);
  revalidatePath(reviewHref(slug));
  const query = error ? `${page.includes("?") ? "&" : "?"}error=${error}` : "";
  redirect(`${page}${query}${error ? "#notice" : ""}`);
}

function errorOf(result: Awaited<ReturnType<typeof apiSend>>): ReviewError | null {
  return result.ok ? null : reviewError(refusalCode(result), result.status);
}

/** A comment's text as the API counts it: line breaks as one character, no blank space around. */
function bodyOf(formData: FormData): string | null {
  const body = field(formData, "body").replace(/\r\n?/g, "\n").trim();
  return body.length >= 1 && body.length <= COMMENT_MAX ? body : null;
}

/** What a comment form shows after a refusal; the text typed stays in the form. */
export type CommentState = { error: ReviewError | null };

/**
 * Writes a comment: a new one on a round, or its author's new text for one (`comment`). Back to the
 * round once written; a refusal comes back to the form instead, so that the text is not lost.
 */
export async function saveComment(_: CommentState, formData: FormData): Promise<CommentState> {
  const target = roundTarget(formData);
  const comment = field(formData, "comment") ? idOf(formData, "comment") : undefined;
  if (!target || comment === null) return { error: "failed" };
  const body = bodyOf(formData);
  if (body === null) return { error: "comment_invalid" };
  const result = comment
    ? await apiSend(`/teams/${target.slug}/comments/${comment}`, "PATCH", { body })
    : await apiSend(
        `/teams/${target.slug}/matches/${target.match}/rounds/${target.round}/comments`,
        "POST",
        { body },
      );
  const error = errorOf(result);
  if (error) return { error };
  backToRound(target, null);
}

/** Deletes a comment: its author's, or anyone's for a member who manages the review. */
export async function deleteComment(formData: FormData): Promise<void> {
  const target = roundTarget(formData);
  const comment = idOf(formData, "comment");
  if (!target || !comment) return;
  const result = await apiSend(`/teams/${target.slug}/comments/${comment}`, "DELETE");
  backToRound(target, errorOf(result));
}

/** The round's tags become those typed (comma separated); an empty field removes them all. */
export async function setTags(formData: FormData): Promise<void> {
  const target = roundTarget(formData);
  if (!target) return;
  const tags = parseTags(field(formData, "tags"));
  if (tags.some((t) => t.length > TAG_MAX)) backToRound(target, "tag_invalid");
  if (tags.length > TAGS_PER_ROUND) backToRound(target, "tag_limit");
  const result = await apiSend(
    `/teams/${target.slug}/matches/${target.match}/rounds/${target.round}/tags`,
    "PUT",
    { tags },
  );
  backToRound(target, errorOf(result));
}

/** Adds the round at the end of one of the team's playlists. */
export async function addToPlaylist(formData: FormData): Promise<void> {
  const target = roundTarget(formData);
  const playlist = idOf(formData, "playlist");
  if (!target || !playlist) return;
  const result = await apiSend(`/teams/${target.slug}/playlists/${playlist}/rounds`, "POST", {
    match_id: target.match,
    round: target.round,
  });
  revalidatePath(reviewHref(target.slug));
  backToRound(target, errorOf(result));
}

/** A playlist's name and description as the API counts them; `null` when out of bounds. */
function playlistText(formData: FormData): { name: string; description: string } | null {
  const name = field(formData, "name").trim().split(/\s+/).join(" ");
  const description = field(formData, "description").trim().split(/\s+/).join(" ");
  if (name.length < 1 || name.length > PLAYLIST_NAME_MAX) return null;
  if (description.length > PLAYLIST_DESCRIPTION_MAX) return null;
  return { name, description };
}

/** Creates a playlist, then shows it. */
export async function createPlaylist(formData: FormData): Promise<void> {
  const slug = slugOf(formData);
  if (!slug) return;
  const text = playlistText(formData);
  if (!text) backToReview(slug, null, "name_invalid");
  const result = await apiSend(`/teams/${slug}/playlists`, "POST", text);
  const id = (result.data as { id?: unknown } | null)?.id;
  backToReview(
    slug,
    result.ok && typeof id === "string" && UUID.test(id) ? id : null,
    errorOf(result),
  );
}

/** Renames a playlist and changes its description. */
export async function updatePlaylist(formData: FormData): Promise<void> {
  const slug = slugOf(formData);
  const playlist = idOf(formData, "playlist");
  if (!slug || !playlist) return;
  const text = playlistText(formData);
  if (!text) backToReview(slug, playlist, "name_invalid");
  const result = await apiSend(`/teams/${slug}/playlists/${playlist}`, "PATCH", text);
  backToReview(slug, playlist, errorOf(result));
}

/** Deletes a playlist (its rounds, comments and tags stay). */
export async function deletePlaylist(formData: FormData): Promise<void> {
  const slug = slugOf(formData);
  const playlist = idOf(formData, "playlist");
  if (!slug || !playlist) return;
  const result = await apiSend(`/teams/${slug}/playlists/${playlist}`, "DELETE");
  backToReview(slug, result.ok ? null : playlist, errorOf(result));
}

/** Takes a round out of a playlist. */
export async function removePlaylistRound(formData: FormData): Promise<void> {
  const slug = slugOf(formData);
  const playlist = idOf(formData, "playlist");
  const match = idOf(formData, "match");
  const round = roundOf(formData);
  if (!slug || !playlist || !match || !round) return;
  const result = await apiSend(
    `/teams/${slug}/playlists/${playlist}/rounds/${match}/${round}`,
    "DELETE",
  );
  backToReview(slug, playlist, errorOf(result));
}

/** Moves a round of a playlist one place up or down, in the order the API gives now: the round
 * is found by its match and number, so that a change made meanwhile (or a second click) moves it,
 * and not whatever round now sits where it was. */
export async function movePlaylistRound(formData: FormData): Promise<void> {
  const slug = slugOf(formData);
  const playlist = idOf(formData, "playlist");
  const match = idOf(formData, "match");
  const round = roundOf(formData);
  const by = field(formData, "by");
  if (!slug || !playlist || !match || !round || (by !== "up" && by !== "down")) return;
  const found = await findPlaylist(slug, playlist);
  if (!found) backToReview(slug, playlist, "failed");
  const index = found.items.findIndex((i) => i.match_id === match && i.round === round);
  if (index < 0) backToReview(slug, playlist, "gone");
  const result = await apiSend(`/teams/${slug}/playlists/${playlist}/order`, "PUT", {
    rounds: moved(found.items, index, by === "up" ? -1 : 1),
  });
  backToReview(slug, playlist, errorOf(result));
}
