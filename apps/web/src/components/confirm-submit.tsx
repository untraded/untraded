// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

/**
 * A submit button for an action that cannot be undone in one click: the first click asks, the
 * second one (on "confirm") submits the surrounding form.
 */
export function ConfirmSubmit({
  label,
  question,
  confirm,
  cancel,
  name,
  value,
  size = "default",
}: {
  label: string;
  question: string;
  confirm: string;
  cancel: string;
  /** Sent with the form when confirmed, e.g. `intent=remove`. */
  name?: string;
  value?: string;
  size?: "default" | "sm";
}) {
  const [asking, setAsking] = useState(false);
  if (!asking) {
    return (
      <Button type="button" variant="outline" size={size} onClick={() => setAsking(true)}>
        {label}
      </Button>
    );
  }
  return (
    <span className="flex flex-wrap items-center gap-2">
      <span className="text-sm">{question}</span>
      <Button type="submit" variant="destructive" size={size} name={name} value={value} autoFocus>
        {confirm}
      </Button>
      <Button type="button" variant="ghost" size={size} onClick={() => setAsking(false)}>
        {cancel}
      </Button>
    </span>
  );
}
