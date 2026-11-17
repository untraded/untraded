// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The app's sections: where they live and which pages belong to them. Admin and the team mode
// preview show to admins only (`me.admin`), the player's team to its members; the read-only demo
// (`me.demo`) shows Upload as a preview of what an account gets.

import {
  CalendarDays,
  ChartColumn,
  Crosshair,
  House,
  type LucideIcon,
  MessagesSquare,
  ShieldCheck,
  Sigma,
  SlidersHorizontal,
  TrendingUp,
  Upload,
  Users,
  UsersRound,
} from "lucide-react";

export type Section =
  | "home"
  | "sessions"
  | "matches"
  | "progress"
  | "upload"
  | "formulas"
  | "team"
  | "teams"
  | "stats"
  | "review"
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
  /** The player's own team; its link names the team (`NavLink`'s `href`). */
  teams: { href: "/teams", icon: UsersRound },
  /** A team's stats only: its link gives the team's address (`NavLink`'s `href`). */
  stats: { href: "/teams", icon: ChartColumn },
  /** A team's review: only on a team's pages, whose links give their own address. */
  review: { href: "/teams", icon: MessagesSquare },
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
    "teams",
    "admin",
    "settings",
  ] as const) {
    const { href } = SECTIONS[section];
    if (pathname === href || pathname.startsWith(`${href}/`)) return section;
  }
  return null;
}

/**
 * Folding and unfolding the rail is one movement: the rail's width, the height of its head, the
 * toggle's place and the labels' fade share this duration and this curve (fast start, soft
 * landing). Nothing moves for a player who asked for reduced motion, nor on a touch tablet, whose
 * folded rail is laid out differently (labels under the icons): there the change is immediate.
 * Add the `transition-*` that names what moves.
 */
export const RAIL_MOTION =
  "duration-200 ease-[cubic-bezier(0.2,0,0,1)] motion-reduce:transition-none touch-tablet:transition-none";

/**
 * A tooltip beside its trigger: drawn on hover and on keyboard focus, in CSS only. The parent
 * carries `group/nav` and is positioned. Faded out, it lets the pointer through to the page under
 * it; shown, it takes the pointer, and a bridge over the gap (`before:`) lets the pointer move
 * from the icon onto it without it closing.
 */
export const TOOLTIP =
  "pointer-events-none absolute top-1/2 left-full z-30 ml-3 -translate-y-1/2 rounded-sm border border-chrome-line bg-chrome px-2 py-1 text-[0.8125rem] font-medium whitespace-nowrap text-chrome-foreground opacity-0 shadow-md transition-opacity group-hover/nav:pointer-events-auto group-hover/nav:opacity-100 group-focus-visible/nav:opacity-100 motion-reduce:transition-none before:absolute before:inset-y-0 before:right-full before:w-3";

/**
 * A rail entry's tooltip: on the folded rail only (the default, `data-collapsed="true"` on the
 * shell), and never on a touch screen, which shows the label under the icon. It repeats the
 * label for the eye: mark it `aria-hidden`, the label itself names the entry.
 */
export const RAIL_TOOLTIP = `${TOOLTIP} md:group-data-[collapsed=false]/shell:hidden touch-rail:hidden`;

/**
 * The window a rail entry's label shows through, after the icon. It takes the room the rail
 * leaves: none when folded, so the label is cut by the rail's edge as it moves, and fades with
 * it. Faded out and cut, the label is never hidden: it stays the entry's accessible name. The
 * icon keeps its place in both states, so only the label appears to move.
 */
export const RAIL_CLIP = `min-w-0 flex-1 overflow-hidden opacity-0 transition-opacity md:group-data-[collapsed=false]/shell:opacity-100 ${RAIL_MOTION}`;

/**
 * On a touch screen with the folded rail (`touch-rail`), the label sits under its icon, small, in
 * its short form, like the phone's tabs. Added after `RAIL_CLIP` (the window) and `RAIL_LABEL`
 * (the text), so these win.
 */
export const TOUCH_CLIP =
  "touch-rail:max-w-full touch-rail:flex-none touch-rail:overflow-visible touch-rail:opacity-100 touch-rail:transition-none";

export const RAIL_LABEL =
  "block overflow-hidden pl-2.5 text-[0.9375rem] font-medium text-ellipsis whitespace-nowrap group-aria-[current=page]/nav:font-semibold";

export const TOUCH_LABEL =
  "touch-rail:overflow-visible touch-rail:pl-0 touch-rail:text-center touch-rail:text-[0.6875rem] touch-rail:leading-tight touch-rail:font-normal touch-rail:wrap-anywhere touch-rail:whitespace-normal touch-rail:group-aria-[current=page]/nav:font-semibold";

/** Faded out when the rail is unfolded: what stands in for a label on the folded rail. */
export const FOLDED_ONLY = `transition-opacity md:group-data-[collapsed=false]/shell:opacity-0 ${RAIL_MOTION}`;
