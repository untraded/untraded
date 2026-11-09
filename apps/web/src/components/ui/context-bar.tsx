// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { ReactNode } from "react";

/**
 * The context bar: a strip across the top of the content area, for a page that has a context (the
 * session or match it is about, and its few numbers). The page renders it first, before its own
 * content. It runs edge to edge of the content area while its content lines up with the page's
 * (the shell's content column is a size container, `cqw`), touches the top of the area when it
 * comes first. From 1280 px it holds on one line (a child that may run long scrolls on its own:
 * give it `xl:min-w-0 xl:overflow-x-auto`) and stays in view while scrolling; the page then
 * scrolls a focused element clear of it (`scroll-padding-top` in `globals.css`).
 */
export function ContextBar({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section
      data-context-bar
      aria-label={label}
      className="mx-[calc(50%-50cqw)] mb-6 flex flex-wrap items-center gap-x-6 gap-y-2.5 border-b border-border bg-card px-[calc(50cqw-50%)] py-2.5 first:-mt-6 md:first:-mt-8 xl:sticky xl:top-0 xl:z-10 xl:flex-nowrap"
    >
      {children}
    </section>
  );
}
