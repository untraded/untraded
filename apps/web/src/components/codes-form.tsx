// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { ExternalLink } from "lucide-react";
import { useActionState, useState } from "react";
import { type CodesState, giveCodes } from "@/app/actions";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { type CodeField, type CodeIssue, codeIssue } from "@/lib/codes";
import { STEAM_CODES_HELP } from "@/lib/site";

/** The texts of one field: its name, its format, where to find it and what can go wrong. */
export interface CodeFieldLabels {
  label: string;
  formatHint: string;
  help: string;
  other: string;
  format: string;
  refused: string;
}

export interface CodesLabels {
  auth_code: CodeFieldLabels;
  share_code: CodeFieldLabels;
  helpLink: string;
  map: {
    caption: string;
    note: string;
    auth: string;
    create: string;
    share: string;
  };
  submit: string;
  pending: string;
  errors: Record<NonNullable<CodesState["error"]>, string>;
}

/** How each code is written: shown in its label and as its placeholder. */
const FORMATS: Record<CodeField, string> = {
  auth_code: "AAAA-AAAAA-AAAA",
  share_code: "CSGO-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX",
};
const FIELDS = ["auth_code", "share_code"] as const;
const START: CodesState = { fields: {}, error: null, auth_code: "", share_code: "" };

/**
 * The two codes the collector needs. A field that holds the other code says so as soon as it is
 * typed; a wrong format, once the player leaves the field. The server checks both again, then
 * Steam: a refused code comes back under its own field, other failures above the button.
 */
export function CodesForm({ labels, next }: { labels: CodesLabels; next: string }) {
  const [state, action, pending] = useActionState(giveCodes, START);
  // What the player typed since the last answer, and which fields they have left.
  const [typed, setTyped] = useState<Partial<Record<CodeField, string>>>({});
  const [left, setLeft] = useState<Partial<Record<CodeField, boolean>>>({});
  // A new answer from the server: its verdict wins until the player types again.
  const [answer, setAnswer] = useState(state);
  if (answer !== state) {
    setAnswer(state);
    setTyped({});
  }
  const issue = (field: CodeField): CodeIssue | "refused" | null => {
    const value = typed[field];
    if (value === undefined) return state.fields[field] ?? null;
    const found = codeIssue(field, value);
    return found === "format" && !left[field] ? null : found;
  };
  const input =
    "h-9 w-full max-w-md rounded-md border border-input bg-card px-3 font-mono text-sm aria-invalid:border-destructive";
  return (
    <form action={action} className="flex flex-col gap-5">
      <input type="hidden" name="next" value={next} />
      <div className="flex flex-col gap-2">
        <a
          href={STEAM_CODES_HELP}
          target="_blank"
          rel="noreferrer"
          className="inline-flex w-fit items-center gap-1.5 text-sm text-link underline underline-offset-3"
        >
          {labels.helpLink}
          <ExternalLink aria-hidden="true" className="size-3.5" />
        </a>
        <HelpPageMap labels={labels.map} />
      </div>
      {FIELDS.map((field, n) => {
        const text = labels[field];
        const found = issue(field);
        const error = found ? text[found] : null;
        return (
          <div key={field} className="flex flex-col gap-1.5">
            <label htmlFor={field} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
              <Marker n={n + 1} />
              <span className="font-semibold">{text.label}</span>
              <span
                className="rounded border border-border px-1.5 font-mono text-[0.75rem] font-semibold break-all"
                translate="no"
              >
                {FORMATS[field]}
              </span>
            </label>
            <input
              id={field}
              name={field}
              required
              defaultValue={state[field]}
              autoComplete="off"
              spellCheck={false}
              autoCapitalize={field === "auth_code" ? "characters" : "off"}
              placeholder={FORMATS[field]}
              onChange={(event) => {
                const { value } = event.currentTarget;
                setTyped((current) => ({ ...current, [field]: value }));
              }}
              onBlur={(event) => {
                const { value } = event.currentTarget;
                setLeft((current) => ({ ...current, [field]: true }));
                setTyped((current) => ({ ...current, [field]: value }));
              }}
              aria-invalid={error ? true : undefined}
              aria-describedby={`${field}-format ${field}-help${error ? ` ${field}-error` : ""}`}
              className={input}
            />
            <p id={`${field}-format`} className="text-[0.8125rem]">
              {text.formatHint}
            </p>
            {error && (
              <p
                id={`${field}-error`}
                aria-live="polite"
                className="max-w-prose text-[0.8125rem] font-medium text-destructive"
              >
                {error}
              </p>
            )}
            <p id={`${field}-help`} className="max-w-prose text-[0.8125rem] text-muted-foreground">
              {text.help}
            </p>
          </div>
        );
      })}
      {state.error && (
        <p role="alert" className="max-w-prose text-sm text-destructive">
          {labels.errors[state.error]}
        </p>
      )}
      <Button type="submit" disabled={pending} className="w-fit">
        {pending ? labels.pending : labels.submit}
      </Button>
    </form>
  );
}

/** The number that ties a field to its place on the drawing of Steam's help page. */
function Marker({ n, className }: { n: number; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-grid size-5 shrink-0 place-items-center self-center rounded-full bg-foreground text-[0.6875rem] font-bold text-background",
        className,
      )}
    >
      {n}
    </span>
  );
}

/**
 * A simplified drawing of Steam's help page (not a capture of it): where each code sits. The
 * caption says the same for screen readers; the drawing itself is hidden from them.
 */
function HelpPageMap({ labels }: { labels: CodesLabels["map"] }) {
  const line = "h-1.5 rounded-full bg-muted-foreground/25";
  const zone = "relative rounded-md border-2 border-dashed border-foreground/60 p-2.5 pl-8";
  return (
    <figure className="flex max-w-md flex-col gap-1.5">
      <div
        aria-hidden="true"
        className="overflow-hidden rounded-lg border border-border bg-card text-[0.75rem]"
      >
        <div className="flex items-center gap-1.5 border-b border-border bg-muted px-2.5 py-1.5">
          <span className="size-2 rounded-full bg-muted-foreground/40" />
          <span className="size-2 rounded-full bg-muted-foreground/40" />
          <span className="ml-1.5 truncate rounded bg-card px-2 py-0.5 font-mono text-[0.6875rem] text-muted-foreground">
            help.steampowered.com
          </span>
        </div>
        <div className="flex flex-col gap-2.5 p-3">
          <div className={cn(line, "w-2/3 bg-muted-foreground/40")} />
          <div className={cn(line, "w-11/12")} />
          <div className={zone}>
            <Marker n={1} className="absolute top-2.5 left-2" />
            <p className="font-semibold">{labels.auth}</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <span className="rounded border border-border bg-background px-1.5 py-0.5 font-mono">
                AAAA-AAAAA-AAAA
              </span>
              <span className="rounded bg-muted-foreground/20 px-1.5 py-0.5">{labels.create}</span>
            </div>
          </div>
          <div className={zone}>
            <Marker n={2} className="absolute top-2.5 left-2" />
            <p className="font-semibold">{labels.share}</p>
            <span className="mt-1.5 inline-block max-w-full truncate rounded border border-border bg-background px-1.5 py-0.5 font-mono">
              CSGO-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
            </span>
          </div>
          <div className={cn(line, "w-1/2")} />
        </div>
      </div>
      <figcaption className="text-[0.8125rem]">
        {labels.caption} <span className="text-muted-foreground">{labels.note}</span>
      </figcaption>
    </figure>
  );
}
