// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { OctagonX } from "lucide-react";
import { useActionState, useState } from "react";
import { type CommentState, saveComment } from "@/app/teams/review-actions";
import { HiddenFields } from "@/components/hidden-fields";
import { Button } from "@/components/ui/button";
import { COMMENT_MAX, type ReviewError } from "@/lib/review";

const START: CommentState = { error: null };

/**
 * A comment's form: a new comment on a round, or its author's edit of one (`values.comment`). The
 * text is held here, so that a refusal (too long, the round's limit reached, the server away)
 * leaves it in the field with the reason under it; once written, the page comes back to the round.
 */
export function CommentForm({
  id,
  values,
  initial = "",
  rows,
  labels,
}: {
  id: string;
  values: Record<string, string | number>;
  initial?: string;
  rows: number;
  labels: {
    field: string;
    /** Hide the field's label, its name being given by the context (an edit). */
    hiddenLabel?: boolean;
    submit: string;
    /** The submit button's full name, which says which round or comment it is for. */
    submitName: string;
    errors: Record<ReviewError, string>;
  };
}) {
  const [state, action, pending] = useActionState(saveComment, START);
  const [text, setText] = useState(initial);
  const error = `${id}-error`;
  return (
    <form action={action} className="flex flex-col gap-2">
      <HiddenFields values={values} />
      <label htmlFor={id} className={labels.hiddenLabel ? "sr-only" : "text-xs font-medium"}>
        {labels.field}
      </label>
      <textarea
        id={id}
        name="body"
        required
        maxLength={COMMENT_MAX}
        rows={rows}
        value={text}
        onChange={(event) => setText(event.target.value)}
        aria-invalid={state.error ? true : undefined}
        aria-describedby={state.error ? error : undefined}
        className="min-h-16 w-full rounded-md border border-input bg-card px-3 py-2 text-sm aria-invalid:border-destructive"
      />
      {state.error && (
        <p id={error} role="alert" className="flex items-start gap-2 text-sm text-destructive">
          <OctagonX aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {labels.errors[state.error]}
        </p>
      )}
      <Button
        type="submit"
        size="sm"
        disabled={pending}
        aria-label={labels.submitName}
        className="self-start"
      >
        {labels.submit}
      </Button>
    </form>
  );
}
