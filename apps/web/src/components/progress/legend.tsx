// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

/** What the curves draw: the player's line, plain, and the reference's, dashed (decorative: the
 * table under each curve names both). Also drawn by the page's skeleton. */
export function Legend({ you, reference }: { you: string; reference: string }) {
  return (
    <span
      aria-hidden="true"
      className="flex shrink-0 gap-3.5 text-xs text-muted-foreground lg:ml-auto"
    >
      <span className="inline-flex items-center gap-1.5">
        <span className="w-4 border-t-2 border-foreground" />
        {you}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="w-4 border-t-2 border-dashed border-muted-foreground" />
        {reference}
      </span>
    </span>
  );
}
