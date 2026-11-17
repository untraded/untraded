// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronRight, MessageSquare, OctagonX, Play } from "lucide-react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { addToPlaylist, deleteComment, setTags } from "@/app/teams/review-actions";
import { ConfirmSubmit } from "@/components/confirm-submit";
import { HiddenFields } from "@/components/hidden-fields";
import { CommentForm } from "@/components/teams/comment-form";
import { Button, buttonVariants } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type { Locale } from "@/i18n/locale";
import type { MatchDetail, MatchReview, ReviewComment, Round } from "@/lib/api";
import { cn } from "@/lib/cn";
import { dateTime } from "@/lib/format";
import {
  REVIEW_ERRORS,
  type ReviewError,
  reviewHref,
  roundAnchor,
  TAG_MAX,
  TAGS_PER_ROUND,
  viewerHref,
} from "@/lib/review";

type T = (key: string, values?: Record<string, string | number>) => string;

const FIELD = "w-full rounded-md border border-input bg-card px-3 text-sm";

/**
 * The team's review of a match, round by round: each round a fold (closed, but for the one an
 * action came back to), its line saying the result from our side, its tags and how many comments it
 * has; open, its comments, and for the roles allowed to, the forms to comment, to tag and to add it
 * to a playlist. Every text a player wrote is shown as text, line breaks kept: never as markup.
 */
export async function RoundReview({
  slug,
  match,
  review,
  open,
  error,
  readOnly,
  locale,
  timeZone,
}: {
  slug: string;
  match: MatchDetail;
  /** `null` when the API could not give it: the page stands without. */
  review: MatchReview | null;
  /** The round an action came back to: its fold opens. */
  open: number | null;
  error: ReviewError | null;
  /** The read-only demo: no form at all. */
  readOnly: boolean;
  locale: Locale;
  timeZone: string;
}) {
  const t = await getTranslations("teamReview");
  if (!review) {
    return (
      <Panel title={t("title")}>
        <p className="text-sm text-muted-foreground">{t("unavailable")}</p>
      </Panel>
    );
  }
  const may = {
    comment: !readOnly && review.permissions.comment,
    manage: !readOnly && review.permissions.manage,
  };
  const comments = new Map<number, ReviewComment[]>();
  for (const found of review.comments) {
    // The read-only demo changes nothing, whatever its role says.
    const c = readOnly ? { ...found, can_edit: false, can_delete: false } : found;
    comments.set(c.round, [...(comments.get(c.round) ?? []), c]);
  }
  const tags = new Map(review.tags.map((r) => [r.round, r.tags]));
  const errors = Object.fromEntries(REVIEW_ERRORS.map((e) => [e, t(`errors.${e}`)])) as Record<
    ReviewError,
    string
  >;
  // An action that came back to a round the match does not have (any more): said above the rounds.
  const astray = error !== null && !match.rounds.some((r) => r.round === open);
  return (
    <Panel
      title={t("title")}
      aside={
        <span className="tabular-nums">
          {t("summary", { comments: review.comments.length, tagged: review.tags.length })}
        </span>
      }
      flush
    >
      <p className="border-b border-line-soft px-3.5 py-2 text-xs text-muted-foreground">
        {t("lead")}
      </p>
      {astray && error && (
        <p
          role="alert"
          className="flex items-start gap-2 border-b border-line-soft px-3.5 py-2 text-sm text-destructive"
        >
          <OctagonX aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {errors[error]}
        </p>
      )}
      <ul>
        {match.rounds.map((round) => (
          <RoundFold
            key={round.round}
            slug={slug}
            match={match}
            round={round}
            comments={comments.get(round.round) ?? []}
            tags={tags.get(round.round) ?? []}
            playlists={review.playlists}
            open={open === round.round}
            error={open === round.round ? error : null}
            may={may}
            errors={errors}
            locale={locale}
            timeZone={timeZone}
            t={t}
          />
        ))}
      </ul>
    </Panel>
  );
}

function RoundFold({
  slug,
  match,
  round,
  comments,
  tags,
  playlists,
  open,
  error,
  may,
  errors,
  locale,
  timeZone,
  t,
}: {
  slug: string;
  match: MatchDetail;
  round: Round;
  comments: ReviewComment[];
  tags: string[];
  playlists: MatchReview["playlists"];
  open: boolean;
  error: ReviewError | null;
  may: { comment: boolean; manage: boolean };
  errors: Record<ReviewError, string>;
  locale: Locale;
  timeZone: string;
  t: T;
}) {
  const ours = match.my_team;
  const won = ours && round.winner_team ? round.winner_team === ours : null;
  const side = ours ? (round.ct_team === ours ? "CT" : "T") : null;
  const holding = playlists.filter((p) => p.rounds.includes(round.round));
  const free = playlists.filter((p) => !p.rounds.includes(round.round));
  const hidden = { slug, match: match.id, round: round.round };
  return (
    <li
      id={roundAnchor(round.round)}
      className="scroll-mt-20 border-b border-line-soft last:border-b-0"
    >
      <details open={open} className="group">
        <summary className="flex min-h-11 cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1 px-3.5 py-2 hover:bg-muted/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
          <ChevronRight
            aria-hidden="true"
            className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90 motion-reduce:transition-none"
          />
          <span className="w-20 shrink-0 text-sm font-medium tabular-nums">
            {t("round", { round: round.round })}
          </span>
          <span className="w-24 shrink-0 text-xs text-muted-foreground">
            {won === null ? (side ?? "") : t(won ? "won" : "lost", { side: side ?? "" })}
          </span>
          {tags.length > 0 && (
            <span className="flex min-w-0 flex-wrap gap-1">
              {tags.map((tag) => (
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
          {comments.length > 0 && (
            <span className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground tabular-nums">
              <MessageSquare aria-hidden="true" className="size-3.5" />
              {t("comments", { count: comments.length })}
            </span>
          )}
        </summary>

        <div className="flex flex-col gap-4 px-3.5 pt-1 pb-4 sm:pl-10">
          {error && (
            <p
              role="alert"
              className="flex items-start gap-2 rounded-md border border-destructive/40 px-3 py-2 text-sm text-destructive"
            >
              <OctagonX aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              {t(`errors.${error}`)}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[0.8125rem]">
            <Link
              href={viewerHref(match.id, round.round)}
              className="inline-flex items-center gap-1 text-link underline underline-offset-3"
            >
              <Play aria-hidden="true" className="size-3.5" />
              {t("viewer")}
            </Link>
            {holding.length > 0 && (
              <span className="text-muted-foreground">
                {t("inPlaylists")}{" "}
                {holding.map((p, i) => (
                  <span key={p.id}>
                    {i > 0 && ", "}
                    <Link
                      href={reviewHref(slug, p.id)}
                      className="text-link underline underline-offset-3"
                    >
                      {p.name}
                    </Link>
                  </span>
                ))}
              </span>
            )}
          </div>

          {comments.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("noComment")}</p>
          ) : (
            <ol
              className="flex flex-col gap-3"
              aria-label={t("commentsOf", { round: round.round })}
            >
              {comments.map((c) => (
                <CommentItem
                  key={c.id}
                  comment={c}
                  hidden={hidden}
                  errors={errors}
                  locale={locale}
                  timeZone={timeZone}
                  t={t}
                />
              ))}
            </ol>
          )}

          {may.comment && (
            <CommentForm
              id={`comment-${round.round}`}
              values={hidden}
              rows={2}
              labels={{
                field: t("addComment"),
                submit: t("send"),
                submitName: t("sendOf", { round: round.round }),
                errors,
              }}
            />
          )}

          {may.manage && (
            <div className="grid gap-3 lg:grid-cols-2">
              <form action={setTags} className="flex flex-col gap-1.5">
                <HiddenFields values={hidden} />
                <label htmlFor={`tags-${round.round}`} className="text-xs font-medium">
                  {t("tags")}
                </label>
                <div className="flex gap-2">
                  <input
                    id={`tags-${round.round}`}
                    name="tags"
                    defaultValue={tags.join(", ")}
                    maxLength={TAGS_PER_ROUND * (TAG_MAX + 2)}
                    aria-describedby={`tags-hint-${round.round}`}
                    className={cn(FIELD, "h-8 min-w-0")}
                  />
                  <Button
                    type="submit"
                    size="sm"
                    variant="outline"
                    aria-label={t("saveTagsOf", { round: round.round })}
                  >
                    {t("save")}
                  </Button>
                </div>
                <p id={`tags-hint-${round.round}`} className="text-xs text-muted-foreground">
                  {t("tagsHint", { count: TAGS_PER_ROUND, length: TAG_MAX })}
                </p>
              </form>
              {playlists.length === 0 ? (
                <p className="self-end text-xs text-muted-foreground">
                  {t("noPlaylist")}{" "}
                  <Link href={reviewHref(slug)} className="text-link underline underline-offset-3">
                    {t("createPlaylist")}
                  </Link>
                </p>
              ) : free.length > 0 ? (
                <form action={addToPlaylist} className="flex flex-col gap-1.5">
                  <HiddenFields values={hidden} />
                  <label htmlFor={`playlist-${round.round}`} className="text-xs font-medium">
                    {t("addToPlaylist")}
                  </label>
                  <div className="flex gap-2">
                    <select
                      id={`playlist-${round.round}`}
                      name="playlist"
                      className={cn(FIELD, "h-8 min-w-0")}
                    >
                      {free.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                    <Button
                      type="submit"
                      size="sm"
                      variant="outline"
                      aria-label={t("addToPlaylistOf", { round: round.round })}
                    >
                      {t("add")}
                    </Button>
                  </div>
                </form>
              ) : (
                <p className="self-end text-xs text-muted-foreground">{t("inEveryPlaylist")}</p>
              )}
            </div>
          )}
        </div>
      </details>
    </li>
  );
}

function CommentItem({
  comment,
  hidden,
  errors,
  locale,
  timeZone,
  t,
}: {
  comment: ReviewComment;
  hidden: Record<string, string | number>;
  errors: Record<ReviewError, string>;
  locale: Locale;
  timeZone: string;
  t: T;
}) {
  const author = comment.author_name ?? t("formerMember");
  return (
    <li className="flex flex-col gap-1">
      <p className="flex flex-wrap items-baseline gap-x-2 text-xs text-muted-foreground">
        <span
          className={cn(
            "font-medium text-foreground",
            comment.author_name === null && "italic text-muted-foreground",
          )}
        >
          {comment.mine ? t("you") : author}
        </span>
        <time dateTime={comment.created_at}>{dateTime(comment.created_at, locale, timeZone)}</time>
        {comment.edited_at && <span>{t("edited")}</span>}
        {comment.tick !== null && (
          <Link
            href={viewerHref(comment.match_id, comment.round, comment.tick)}
            className="text-link underline underline-offset-3"
          >
            {t("atInstant")}
          </Link>
        )}
      </p>
      <p className="text-sm break-words whitespace-pre-wrap">{comment.body}</p>
      {(comment.can_edit || comment.can_delete) && (
        <div className="flex flex-wrap items-start gap-2">
          {comment.can_edit && (
            <details className="open:w-full">
              <summary
                className={cn(
                  buttonVariants({ variant: "outline", size: "sm" }),
                  "cursor-pointer list-none [&::-webkit-details-marker]:hidden",
                )}
              >
                {t("edit")}
              </summary>
              <div className="mt-1.5 sm:w-[32rem]">
                <CommentForm
                  id={`edit-${comment.id}`}
                  values={{ ...hidden, comment: comment.id }}
                  initial={comment.body}
                  rows={3}
                  labels={{
                    field: t("editLabel"),
                    hiddenLabel: true,
                    submit: t("save"),
                    submitName: t("saveComment"),
                    errors,
                  }}
                />
              </div>
            </details>
          )}
          {comment.can_delete && (
            <form action={deleteComment}>
              <HiddenFields values={{ ...hidden, comment: comment.id }} />
              <ConfirmSubmit
                label={t("delete")}
                question={t("deleteQuestion")}
                confirm={t("deleteConfirm")}
                cancel={t("cancel")}
                size="sm"
              />
            </form>
          )}
        </div>
      )}
    </li>
  );
}
