// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The app's sections: where they live and which pages belong to them. Only sections whose page
// exists are listed; Import joins when it is built. Admin and the team mode
// preview show to admins only (`me.admin`).

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
 * Sidebar labels: visible on wide screens unless the sidebar is folded (`data-collapsed` on the
 * shell), screen-reader only otherwise. Between 768 and 1024 px the sidebar is always folded.
 */
export const SIDEBAR_LABEL = "sr-only lg:not-sr-only lg:group-data-[collapsed=true]/shell:sr-only";
