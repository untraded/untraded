// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { ExternalLink } from "lucide-react";
import { useActionState } from "react";
import { type CodesState, giveCodes } from "@/app/actions";
import { Button } from "@/components/ui/button";
import { STEAM_CODES_HELP } from "@/lib/site";

export interface CodesLabels {
  authLabel: string;
  authHelp: string;
  shareLabel: string;
  shareHelp: string;
  helpLink: string;
  submit: string;
  pending: string;
  errors: Record<NonNullable<CodesState["error"]>, string>;
}

const START: CodesState = { error: null, auth_code: "", share_code: "" };

/**
 * The two codes the collector needs, checked with Steam by the API: a refused code comes back
 * under its own field, with what the player typed; other failures above the button.
 */
export function CodesForm({ labels, next }: { labels: CodesLabels; next: string }) {
  const [state, action, pending] = useActionState(giveCodes, START);
  const fieldError = (field: "auth_code" | "share_code") =>
    state.error === field ? labels.errors[field] : null;
  const formError =
    state.error && state.error !== "auth_code" && state.error !== "share_code"
      ? labels.errors[state.error]
      : null;
  const input =
    "h-9 w-full max-w-md rounded-md border border-input bg-card px-3 font-mono text-sm aria-invalid:border-destructive";
  return (
    <form action={action} className="flex flex-col gap-5">
      <input type="hidden" name="next" value={next} />
      <a
        href={STEAM_CODES_HELP}
        target="_blank"
        rel="noreferrer"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-link underline underline-offset-3"
      >
        {labels.helpLink}
        <ExternalLink aria-hidden="true" className="size-3.5" />
      </a>
      {(["auth_code", "share_code"] as const).map((field) => {
        const error = fieldError(field);
        const label = field === "auth_code" ? labels.authLabel : labels.shareLabel;
        const help = field === "auth_code" ? labels.authHelp : labels.shareHelp;
        return (
          <div key={field} className="flex flex-col gap-1.5">
            <label htmlFor={field} className="text-sm font-semibold">
              {label}
            </label>
            <input
              id={field}
              name={field}
              required
              defaultValue={state[field]}
              autoComplete="off"
              spellCheck={false}
              autoCapitalize={field === "auth_code" ? "characters" : "off"}
              placeholder={field === "auth_code" ? "AAAA-AAAAA-AAAA" : "CSGO-XXXXX-XXXXX-…"}
              aria-invalid={error ? true : undefined}
              aria-describedby={`${field}-help${error ? ` ${field}-error` : ""}`}
              className={input}
            />
            <p id={`${field}-help`} className="max-w-prose text-[0.8125rem] text-muted-foreground">
              {help}
            </p>
            {error && (
              <p id={`${field}-error`} className="text-[0.8125rem] text-destructive">
                {error}
              </p>
            )}
          </div>
        );
      })}
      {formError && (
        <p role="alert" className="max-w-prose text-sm text-destructive">
          {formError}
        </p>
      )}
      <Button type="submit" disabled={pending} className="w-fit">
        {pending ? labels.pending : labels.submit}
      </Button>
    </form>
  );
}
