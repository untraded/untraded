// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Check, Copy } from "lucide-react";
import { useActionState, useEffect, useId, useState } from "react";
import { createInvitation, type InviteLinkState } from "@/app/teams/actions";
import { Button } from "@/components/ui/button";

export interface InviteLinkLabels {
  role: string;
  uses: string;
  usesHint: string;
  create: string;
  ready: string;
  link: string;
  copy: string;
  copied: string;
  errors: Record<string, string>;
}

const START: InviteLinkState = { path: null, error: null };

/**
 * Creates an invitation link: the role it gives and how many people may use it. The link comes
 * back once, in this form's state only: it is shown with a copy button and never read again.
 */
export function InviteLinkForm({
  slug,
  roles,
  defaultRole,
  labels,
}: {
  slug: string;
  roles: { id: string; label: string }[];
  defaultRole: string | undefined;
  labels: InviteLinkLabels;
}) {
  const [state, action, pending] = useActionState(createInvitation, START);
  // Which link was copied: a new link is not copied yet.
  const [copiedPath, setCopiedPath] = useState<string | null>(null);
  const [origin, setOrigin] = useState("");
  const id = useId();
  useEffect(() => setOrigin(window.location.origin), []);
  const copied = state.path !== null && copiedPath === state.path;
  const link = state.path ? `${origin}${state.path}` : null;
  const control = "h-9 rounded-md border border-input bg-card px-2.5 text-sm";
  return (
    <div className="flex flex-col gap-3">
      <form action={action} className="flex flex-wrap items-end gap-3">
        <input type="hidden" name="slug" value={slug} />
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-role`} className="text-sm font-medium">
            {labels.role}
          </label>
          <select
            id={`${id}-role`}
            name="role_id"
            defaultValue={defaultRole}
            className={`${control} min-w-36`}
          >
            {roles.map((role) => (
              <option key={role.id} value={role.id}>
                {role.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-uses`} className="text-sm font-medium">
            {labels.uses}
          </label>
          <input
            id={`${id}-uses`}
            name="max_uses"
            type="number"
            inputMode="numeric"
            autoComplete="off"
            min={1}
            max={20}
            defaultValue={5}
            required
            aria-describedby={`${id}-uses-hint`}
            className={`${control} w-24 tabular-nums`}
          />
        </div>
        <Button type="submit" disabled={pending}>
          {labels.create}
        </Button>
        <p id={`${id}-uses-hint`} className="basis-full text-xs text-muted-foreground">
          {labels.usesHint}
        </p>
      </form>
      <div aria-live="polite">
        {state.error ? (
          <p className="text-sm text-destructive">
            {labels.errors[state.error] ?? labels.errors.failed}
          </p>
        ) : link ? (
          <div className="flex flex-col gap-2 rounded-md border border-border border-l-[3px] border-l-highlight bg-background p-3">
            <p className="text-sm font-medium">{labels.ready}</p>
            <div className="flex flex-wrap items-center gap-2">
              <label htmlFor={`${id}-link`} className="sr-only">
                {labels.link}
              </label>
              <input
                id={`${id}-link`}
                readOnly
                value={link}
                spellCheck={false}
                translate="no"
                onFocus={(e) => e.currentTarget.select()}
                className={`${control} min-w-0 flex-1 basis-64 font-mono text-[0.8125rem]`}
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  const select = () => {
                    setCopiedPath(null);
                    const input = document.getElementById(`${id}-link`);
                    if (input instanceof HTMLInputElement) input.select();
                  };
                  // No clipboard outside a secure context (a server on plain http).
                  if (!navigator.clipboard) return select();
                  navigator.clipboard.writeText(link).then(() => setCopiedPath(state.path), select);
                }}
              >
                {copied ? (
                  <Check data-icon="inline-start" aria-hidden="true" />
                ) : (
                  <Copy data-icon="inline-start" aria-hidden="true" />
                )}
                {copied ? labels.copied : labels.copy}
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
