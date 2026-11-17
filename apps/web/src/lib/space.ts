// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The workspace the site shows: a team's pages (`/teams/<slug>/…`) are that team's space, every
// other page is the player's own. The rail, the phone's tabs and the switch follow it.

/** A team's space, read from the address: its slug when it is one of the player's teams, else
 * `null` (the player's own space). */
export function spaceOf(pathname: string, slugs: readonly string[]): string | null {
  const found = /^\/teams\/([^/?#]+)/.exec(pathname);
  if (!found?.[1]) return null;
  let segment: string;
  try {
    segment = decodeURIComponent(found[1]).toLowerCase();
  } catch {
    return null;
  }
  return slugs.find((slug) => slug.toLowerCase() === segment) ?? null;
}

/** The player's own space, in the switch and the cookie: `~` keeps it from ever being a team's
 * slug (`[a-z0-9-]`), so a team named `personal` stays a team. */
export const PERSONAL_SPACE = "~personal";

/** The team the player last opened, from the cookie: `null` for their own space, or a slug that is
 * no longer one of their teams. */
export function rememberedTeam(
  cookie: string | undefined,
  slugs: readonly string[],
): string | null {
  if (!cookie || cookie === PERSONAL_SPACE) return null;
  return slugs.find((slug) => slug.toLowerCase() === cookie.toLowerCase()) ?? null;
}

/** A team's initials for its badge: the first letters of its first two words ("Northwind" "NO",
 * "Ashgrove Academy" "AA"), in capitals. */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const letters =
    words.length === 1
      ? Array.from(words[0] ?? "").slice(0, 2)
      : words.slice(0, 2).map((w) => Array.from(w)[0] ?? "");
  return letters.join("").toLocaleUpperCase();
}
