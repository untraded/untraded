// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

const PULSE = "animate-pulse rounded-[3px] bg-muted motion-reduce:animate-none";

/**
 * A muted block standing for content on its way: a chart, a button, a box. Never the accent,
 * which is kept for actions and selection. Still for players who ask for reduced motion.
 */
export function Skeleton({ className }: { className?: string }) {
  return <span aria-hidden="true" className={cn("block", PULSE, className)} />;
}

/**
 * One line of text on its way. `className` takes the real text's size classes, so the line is
 * exactly as tall as the text it stands for (its line box comes from that font size and line
 * height); `width` is the bar's width.
 */
export function SkeletonLine({
  className,
  width = "w-32",
}: {
  className?: string;
  width?: string;
}) {
  return (
    <span aria-hidden="true" className={cn("block", className)}>
      <span className={cn("inline-block h-[0.75em] max-w-full align-middle", PULSE, width)} />
    </span>
  );
}

/**
 * A page or a part of one that is loading: busy for assistive technologies, with a hidden
 * "Loading…" read out. `announce` is off for the parts that stream in below an already loaded
 * page, so a screen reader is not told several times.
 */
export async function Loading({
  className,
  children,
  announce = true,
}: {
  className?: string;
  children: ReactNode;
  announce?: boolean;
}) {
  const t = await getTranslations("loading");
  return (
    <div aria-busy="true" className={className}>
      <span role={announce ? "status" : undefined} className="sr-only">
        {t("label")}
      </span>
      {children}
    </div>
  );
}

/** Keys for `count` placeholders: they never move, so their position is their identity. */
export function slots(count: number): string[] {
  return Array.from({ length: count }, (_, i) => `slot-${i}`);
}
