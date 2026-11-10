// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { CircleCheck, CircleDashed, type LucideIcon, OctagonX, TriangleAlert } from "lucide-react";
import type { CheckState } from "@/lib/admin-health";
import { cn } from "@/lib/cn";

/** Each state has an icon of its own shape (circle, triangle, octagon, dashed circle), so that
 * the word and the shape carry it, never the colour alone. */
const ICON: Record<CheckState, LucideIcon> = {
  ok: CircleCheck,
  warn: TriangleAlert,
  fail: OctagonX,
  unknown: CircleDashed,
};
const TONE: Record<CheckState, string> = {
  ok: "text-win",
  warn: "text-foreground",
  fail: "text-destructive",
  unknown: "text-muted-foreground",
};

/** A check's state, as a small chip: an icon and its word. */
export function CheckChip({
  state,
  label,
  className,
}: {
  state: CheckState;
  label: string;
  className?: string;
}) {
  const Icon = ICON[state];
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-sm bg-muted px-2 text-xs font-semibold whitespace-nowrap",
        state === "fail" && "bg-destructive/10",
        TONE[state],
        className,
      )}
    >
      <Icon aria-hidden="true" className="size-3.5 shrink-0" />
      {label}
    </span>
  );
}
