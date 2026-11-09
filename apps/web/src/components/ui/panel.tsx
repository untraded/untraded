// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * A panel, the block of the "Instrument" direction: a title band one step above the panel, with a
 * rule under it, then the body. The band takes the title (a heading, `h2` by default) and, at its
 * right, a short note or the panel's own controls. `flush` drops the body's padding, for a list
 * whose rows run edge to edge. It does not clip its content: a row's focus ring may reach its
 * edges.
 */
export function Panel({
  title,
  aside,
  level = 2,
  flush = false,
  className,
  bodyClassName,
  children,
}: {
  title: ReactNode;
  /** At the right of the band: a note (counts, a unit) or controls (a choice, a link). */
  aside?: ReactNode;
  level?: 2 | 3;
  flush?: boolean;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <section className={cn("rounded-lg border border-border bg-card", className)}>
      <div className="flex min-h-10 flex-wrap items-center justify-between gap-x-3 gap-y-1 rounded-t-[3px] border-b border-border bg-panel-head px-3.5 py-1.5">
        <Heading className="text-[0.8125rem] font-semibold">{title}</Heading>
        {aside && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">{aside}</div>
        )}
      </div>
      <div className={cn(!flush && "px-3.5 py-3", bodyClassName)}>{children}</div>
    </section>
  );
}
