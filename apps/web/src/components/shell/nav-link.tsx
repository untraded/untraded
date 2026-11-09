// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { FOLDED_ONLY, RAIL_TOOLTIP, SECTIONS, type Section, sectionOf, TOUCH_LABEL } from "./nav";
import { PreviewBadge } from "./preview-badge";

/** A section link, marked when the current page belongs to it: on the rail or a phone tab. */
export function NavLink({
  section,
  label,
  short,
  badge,
  place,
}: {
  section: Section;
  label: string;
  /** The label in a word or two, shown under the icon on a touch screen's folded rail. */
  short?: string;
  /** A word after the label, e.g. "Preview" for a mock-up. */
  badge?: string;
  place: "rail" | "tab";
}) {
  const current = sectionOf(usePathname()) === section;
  const { href, icon: Icon } = SECTIONS[section];
  if (place === "tab") {
    return (
      <Link
        href={href}
        aria-current={current ? "page" : undefined}
        className="group/tab flex flex-col items-center gap-0.5 pt-2 pb-1 text-[0.6875rem] text-chrome-muted aria-[current=page]:font-semibold aria-[current=page]:text-chrome-foreground"
      >
        <Icon aria-hidden="true" className="size-5 group-aria-[current=page]/tab:text-highlight" />
        {label}
      </Link>
    );
  }
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={cn(
        "group/nav relative flex h-10 shrink-0 items-center justify-center rounded-md text-chrome-muted hover:bg-muted hover:text-chrome-foreground",
        "aria-[current=page]:bg-highlight-soft aria-[current=page]:text-chrome-foreground",
        // The current section also has a bar on its left edge: a shape, not only a colour.
        "aria-[current=page]:before:absolute aria-[current=page]:before:inset-y-2 aria-[current=page]:before:left-0 aria-[current=page]:before:w-[3px] aria-[current=page]:before:rounded-full aria-[current=page]:before:bg-highlight forced-colors:aria-[current=page]:before:bg-[CanvasText]",
        "md:group-data-[collapsed=false]/shell:justify-start md:group-data-[collapsed=false]/shell:gap-2.5 md:group-data-[collapsed=false]/shell:px-2.5",
        "touch-rail:h-auto touch-rail:min-h-12 touch-rail:flex-col touch-rail:gap-1 touch-rail:px-0 touch-rail:py-1.5",
      )}
    >
      <Icon
        aria-hidden="true"
        className="size-[18px] shrink-0 group-aria-[current=page]/nav:text-highlight"
      />
      {badge && (
        // On the folded rail, a dot on the icon says the section is a preview; its word is in the
        // tooltip.
        <span
          aria-hidden="true"
          className={cn(
            "absolute top-2 right-2.5 size-1.5 rounded-full bg-chrome-muted touch-rail:top-1.5 touch-rail:right-auto touch-rail:left-[calc(50%+6px)]",
            FOLDED_ONLY,
          )}
        />
      )}
      <span className={cn(RAIL_TOOLTIP, TOUCH_LABEL)}>
        {short && short !== label ? (
          // On a touch screen's folded rail, the short label shows, first, and the full one is
          // read after it: the visible word stays part of the name (voice control: "tap Upload").
          <>
            <span className="hidden touch-rail:inline">{short}</span>
            <span className="touch-rail:sr-only">
              <span className="hidden touch-rail:inline">, </span>
              {label}
            </span>
          </>
        ) : (
          label
        )}
        {/* A space, so that the accessible name reads "Team Preview", not "TeamPreview". */}
        {badge && (
          <>
            {" "}
            <PreviewBadge label={badge} className="ml-1 touch-rail:sr-only" />
          </>
        )}
      </span>
    </Link>
  );
}
