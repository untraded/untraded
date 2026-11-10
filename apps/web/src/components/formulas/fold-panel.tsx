// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * A panel one can fold, in the look of `Panel`: its title band is the `<summary>` (a chevron, the
 * title as an `h2`, a short note at its right), with the rule under it only while the panel is
 * open. No script: the browser's own `<details>`, which a search in the page also opens.
 */
export function FoldPanel({
  title,
  aside,
  open = false,
  id,
  bodyClassName,
  children,
}: {
  title: ReactNode;
  /** At the right of the band: a short note, such as a count. */
  aside?: ReactNode;
  open?: boolean;
  id?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  return (
    <details
      id={id}
      open={open}
      className="group scroll-mt-4 rounded-lg border border-border bg-card"
    >
      <summary className="flex min-h-10 cursor-pointer list-none items-center gap-2.5 rounded-[3px] bg-panel-head px-3.5 py-1.5 select-none hover:bg-muted group-open:rounded-b-none group-open:border-b group-open:border-border [&::-webkit-details-marker]:hidden">
        <ChevronRight
          aria-hidden="true"
          className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90 motion-reduce:transition-none"
        />
        <h2 className="text-[0.8125rem] font-semibold">{title}</h2>
        {aside && (
          <span className="ml-auto text-xs text-muted-foreground tabular-nums">{aside}</span>
        )}
      </summary>
      <div className={cn(bodyClassName)}>{children}</div>
    </details>
  );
}
