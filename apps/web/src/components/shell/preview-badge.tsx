// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { cn } from "@/lib/cn";

/** "Preview": a section that is a mock-up, not a working feature yet. */
export function PreviewBadge({ label, className }: { label: string; className?: string }) {
  return (
    <span
      className={cn(
        "rounded-sm border border-border px-1.5 py-px align-middle text-[0.6875rem] font-medium text-muted-foreground",
        className,
      )}
    >
      {label}
    </span>
  );
}
