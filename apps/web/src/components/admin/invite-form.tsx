// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { useActionState } from "react";
import { type InviteState, invite } from "@/app/admin/actions";
import { Button } from "@/components/ui/button";

export interface InviteLabels {
  title: string;
  steamId: string;
  steamIdHelp: string;
  displayName: string;
  submit: string;
  /** The confirmation, with a literal `{name}` the form replaces by the invited player's name. */
  invited: string;
  errors: Record<NonNullable<InviteState["error"]>, string>;
}

const START: InviteState = { error: null, invited: null, steam_id: "", display_name: "" };

/** Invites a Steam account: a refused field comes back under its input. */
export function InviteForm({ labels }: { labels: InviteLabels }) {
  const [state, action, pending] = useActionState(invite, START);
  const error = (field: "steam_id" | "display_name") =>
    state.error === field ? labels.errors[field] : null;
  const other =
    state.error === "exists" || state.error === "failed" ? labels.errors[state.error] : null;
  const input =
    "h-9 w-full rounded-md border border-input bg-card px-3 text-sm aria-invalid:border-destructive";
  return (
    <form
      action={action}
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4"
    >
      <h2 className="font-semibold">{labels.title}</h2>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,14rem)_minmax(0,14rem)_auto] sm:items-start">
        <div className="flex flex-col gap-1">
          <label htmlFor="steam_id" className="text-sm font-medium">
            {labels.steamId}
          </label>
          <input
            id="steam_id"
            name="steam_id"
            required
            inputMode="numeric"
            autoComplete="off"
            spellCheck={false}
            defaultValue={state.steam_id}
            placeholder="7656119…"
            aria-invalid={error("steam_id") ? true : undefined}
            aria-describedby="steam_id-help"
            className={`${input} font-mono`}
          />
          <p
            id="steam_id-help"
            className={`text-xs ${error("steam_id") ? "text-destructive" : "text-muted-foreground"}`}
          >
            {error("steam_id") ?? labels.steamIdHelp}
          </p>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="display_name" className="text-sm font-medium">
            {labels.displayName}
          </label>
          <input
            id="display_name"
            name="display_name"
            required
            maxLength={64}
            autoComplete="off"
            defaultValue={state.display_name}
            aria-invalid={error("display_name") ? true : undefined}
            aria-describedby={error("display_name") ? "display_name-error" : undefined}
            className={input}
          />
          {error("display_name") && (
            <p id="display_name-error" className="text-xs text-destructive">
              {error("display_name")}
            </p>
          )}
        </div>
        <Button type="submit" disabled={pending} className="sm:mt-6">
          {labels.submit}
        </Button>
      </div>
      <p aria-live="polite" className="text-sm">
        {other ? (
          <span className="text-destructive">{other}</span>
        ) : state.invited ? (
          labels.invited.replace("{name}", state.invited)
        ) : null}
      </p>
    </form>
  );
}
