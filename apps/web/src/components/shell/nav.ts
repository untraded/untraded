// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The app's sections: where they live and which pages belong to them. Admin and the team mode
// preview show to admins only (`me.admin`); the read-only demo (`me.demo`) shows Upload as a
// preview of what an account gets.

import {
  CalendarDays,
  Crosshair,
  House,
  type LucideIcon,
  ShieldCheck,
  Sigma,
  SlidersHorizontal,
  TrendingUp,
  Upload,
  Users,
} from "lucide-react";

export type Section =
  | "home"
  | "sessions"
  | "matches"
  | "progress"
  | "upload"
  | "formulas"
  | "team"
  | "admin"
  | "settings";

export const SECTIONS: Record<Section, { href: string; icon: LucideIcon }> = {
  home: { href: "/", icon: House },
  sessions: { href: "/sessions", icon: CalendarDays },
  matches: { href: "/matches", icon: Crosshair },
  progress: { href: "/progress", icon: TrendingUp },
  upload: { href: "/upload", icon: Upload },
  formulas: { href: "/formulas", icon: Sigma },
  team: { href: "/team", icon: Users },
  admin: { href: "/admin", icon: ShieldCheck },
  settings: { href: "/settings", icon: SlidersHorizontal },
};

/** The section a page belongs to, to mark it in the navigation. */
export function sectionOf(pathname: string): Section | null {
  if (pathname === "/") return "home";
  for (const section of [
    "sessions",
    "matches",
    "progress",
    "upload",
    "formulas",
    "team",
    "admin",
    "settings",
  ] as const) {
    const { href } = SECTIONS[section];
    if (pathname === href || pathname.startsWith(`${href}/`)) return section;
  }
  return null;
}

/**
 * The rail's labels. Folded (the default, `data-collapsed="true"` on the shell), a label is a
 * tooltip beside its icon: drawn on hover and on keyboard focus, in CSS only, and always read by
 * screen readers (it is faded out, never hidden, so it stays the link's accessible name). Unfolded,
 * from 768 px, it sits in the row after the icon. The parent carries `group/nav` and `relative`.
 * `TOOLTIP` alone stays a tooltip when the rail is unfolded. Faded out, it lets the pointer
 * through to the page under it; shown, it takes the pointer, and a bridge over the gap (`before:`)
 * lets the pointer move from the icon onto it without it closing.
 */
export const TOOLTIP =
  "pointer-events-none absolute top-1/2 left-full z-30 ml-3 -translate-y-1/2 rounded-sm border border-chrome-line bg-chrome px-2 py-1 text-[0.8125rem] font-medium whitespace-nowrap text-chrome-foreground opacity-0 shadow-md transition-opacity group-hover/nav:pointer-events-auto group-hover/nav:opacity-100 group-focus-visible/nav:opacity-100 motion-reduce:transition-none before:absolute before:inset-y-0 before:right-full before:w-3";

export const RAIL_TOOLTIP =
  `${TOOLTIP} ` +
  "md:group-data-[collapsed=false]/shell:static md:group-data-[collapsed=false]/shell:ml-0 md:group-data-[collapsed=false]/shell:translate-y-0 md:group-data-[collapsed=false]/shell:border-0 md:group-data-[collapsed=false]/shell:bg-transparent md:group-data-[collapsed=false]/shell:p-0 md:group-data-[collapsed=false]/shell:text-[0.9375rem] md:group-data-[collapsed=false]/shell:text-inherit md:group-data-[collapsed=false]/shell:opacity-100 md:group-data-[collapsed=false]/shell:shadow-none md:group-data-[collapsed=false]/shell:before:hidden md:group-data-[collapsed=false]/shell:group-aria-[current=page]/nav:font-semibold";

/**
 * On a touch screen with the folded rail (`touch-rail`), the label sits under its icon, small, in
 * its short form, like the phone's tabs; no tooltip. Added after `RAIL_TOOLTIP`, so these win.
 */
export const TOUCH_LABEL =
  "touch-rail:static touch-rail:ml-0 touch-rail:translate-y-0 touch-rail:border-0 touch-rail:bg-transparent touch-rail:p-0 touch-rail:text-center touch-rail:text-[0.6875rem] touch-rail:font-normal touch-rail:leading-tight touch-rail:wrap-anywhere touch-rail:whitespace-normal touch-rail:text-inherit touch-rail:opacity-100 touch-rail:shadow-none touch-rail:transition-none touch-rail:before:hidden touch-rail:group-aria-[current=page]/nav:font-semibold";

/** Hidden when the rail is unfolded: what stands in for a label on the folded rail. */
export const FOLDED_ONLY = "md:group-data-[collapsed=false]/shell:hidden";
