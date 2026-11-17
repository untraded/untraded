// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { type InputHTMLAttributes, useActionState } from "react";
import { type CreateTeamState, createTeam } from "@/app/admin/actions";
import { Button } from "@/components/ui/button";

export interface CreateTeamLabels {
  name: string;
  slug: string;
  slugHelp: string;
  owner: string;
  ownerHelp: string;
  submit: string;
  /** The confirmation, with a literal `{name}` the form replaces by the team's name. */
  created: string;
  errors: Record<NonNullable<CreateTeamState["error"]>, string>;
}

const START: CreateTeamState = {
  error: null,
  created: null,
  name: "",
  slug: "",
  owner_steam_id: "",
};

/** Creates a team: its name, its address and its owner. A refused field says so under it. */
export function CreateTeamForm({ labels }: { labels: CreateTeamLabels }) {
  const [state, action, pending] = useActionState(createTeam, START);
  const input =
    "h-9 w-full rounded-md border border-input bg-card px-3 text-sm aria-invalid:border-destructive";
  const error = state.error;
  const slugError =
    error === "slug_invalid" || error === "slug_taken" ? labels.errors[error] : null;
  // A new key each time the form comes back, so that its fields show what the action returned;
  // the message under it stays mounted, so that screen readers announce it.
  const key = `${state.created ?? ""}|${error ?? ""}|${state.slug}`;
  return (
    <div className="flex flex-col gap-3">
      <form
        key={key}
        action={action}
        className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,14rem)_minmax(0,12rem)_minmax(0,14rem)_auto] lg:items-start"
      >
        <Field
          id="team-name"
          name="name"
          label={labels.name}
          defaultValue={state.name}
          error={error === "name" ? labels.errors.name : null}
          className={input}
          maxLength={64}
        />
        <Field
          id="team-slug"
          name="slug"
          label={labels.slug}
          help={labels.slugHelp}
          defaultValue={state.slug}
          error={slugError}
          className={`${input} font-mono`}
          maxLength={32}
        />
        <Field
          id="team-owner"
          name="owner_steam_id"
          label={labels.owner}
          help={labels.ownerHelp}
          defaultValue={state.owner_steam_id}
          error={
            error === "owner_unknown" || error === "owner_format" ? labels.errors[error] : null
          }
          className={`${input} font-mono`}
          inputMode="numeric"
          placeholder="7656119…"
        />
        <Button type="submit" disabled={pending} className="sm:justify-self-start lg:mt-6">
          {labels.submit}
        </Button>
      </form>
      <p aria-live="polite" className="text-sm">
        {error === "failed" ? (
          <span className="text-destructive">{labels.errors.failed}</span>
        ) : state.created ? (
          labels.created.replace("{name}", state.created)
        ) : null}
      </p>
    </div>
  );
}

function Field({
  id,
  label,
  help,
  error,
  ...input
}: {
  id: string;
  label: string;
  help?: string;
  error: string | null;
} & InputHTMLAttributes<HTMLInputElement>) {
  const note = error ?? help;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        required
        autoComplete="off"
        spellCheck={false}
        aria-invalid={error ? true : undefined}
        aria-describedby={note ? `${id}-help` : undefined}
        {...input}
      />
      {note && (
        <p
          id={`${id}-help`}
          className={`text-xs ${error ? "text-destructive" : "text-muted-foreground"}`}
        >
          {note}
        </p>
      )}
    </div>
  );
}
