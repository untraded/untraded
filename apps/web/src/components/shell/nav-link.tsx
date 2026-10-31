// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { SECTIONS, type Section, SIDEBAR_LABEL, sectionOf } from "./nav";
import { PreviewBadge } from "./preview-badge";

/** A section link, marked when the current page belongs to it: in the sidebar or a phone tab. */
export function NavLink({
  section,
  label,
  badge,
  place,
}: {
  section: Section;
  label: string;
  /** A word after the label, e.g. "Preview" for a mock-up. */
  badge?: string;
  place: "sidebar" | "tab";
}) {
  const current = sectionOf(usePathname()) === section;
  const { href, icon: Icon } = SECTIONS[section];
  if (place === "tab") {
    return (
      <Link
        href={href}
        aria-current={current ? "page" : undefined}
        className="group/tab flex flex-col items-center gap-0.5 pt-2 pb-1 text-[0.6875rem] text-muted-foreground aria-[current=page]:font-semibold aria-[current=page]:text-foreground"
      >
        <Icon aria-hidden="true" className="size-5 group-aria-[current=page]/tab:text-highlight" />
        {label}
      </Link>
    );
  }
  return (
    <Link
      href={href}
      title={badge ? `${label} (${badge})` : label}
      aria-current={current ? "page" : undefined}
      className={cn(
        "flex h-9 items-center gap-2.5 rounded-md text-[0.9375rem] whitespace-nowrap text-muted-foreground hover:bg-muted hover:text-foreground",
        "aria-[current=page]:bg-highlight-soft aria-[current=page]:font-semibold aria-[current=page]:text-foreground",
        "justify-center md:justify-start md:px-2.5 md:group-data-[collapsed=true]/shell:justify-center md:group-data-[collapsed=true]/shell:px-0",
      )}
    >
      <Icon aria-hidden="true" className="size-[18px] shrink-0" />
      <span className={SIDEBAR_LABEL}>
        {label}
        {badge && <PreviewBadge label={badge} className="ml-2" />}
      </span>
    </Link>
  );
}
