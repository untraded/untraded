// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { usePathname } from "next/navigation";
import { type ReactNode, useEffect } from "react";
import { SPACE_COOKIE } from "@/i18n/locale";
import { PERSONAL_SPACE, spaceOf } from "@/lib/space";
import type { SpaceLink } from "./space-trigger";

/** The open space's key (`personal`, or a team's slug), read from the address. */
export function useSpaceKey(slugs: readonly string[]): string {
  return spaceOf(usePathname(), slugs) ?? PERSONAL_SPACE;
}

/** The open space among those the switch lists (the player's own when none matches). */
export function useCurrentSpace(spaces: readonly SpaceLink[]): SpaceLink | undefined {
  const key = useSpaceKey(spaces.filter((s) => s.team).map((s) => s.key));
  return spaces.find((s) => s.key === key) ?? spaces[0];
}

/**
 * What the open space shows: the player's own navigation, or the team's. The layout renders both
 * on the server (it is not rendered again on each page); the address picks one here.
 */
export function SpaceSwitch({
  slugs,
  personal,
  teams,
}: {
  slugs: string[];
  personal: ReactNode;
  teams: Record<string, ReactNode>;
}) {
  const key = useSpaceKey(slugs);
  return <>{key === PERSONAL_SPACE ? personal : (teams[key] ?? personal)}</>;
}

/**
 * Remembers the space last opened in a cookie, as the rail's state is: the home page brings the
 * player back to it after signing in. Nothing personal in it: `personal` or a team's slug.
 */
export function SpaceMemory({ slugs }: { slugs: string[] }) {
  const key = useSpaceKey(slugs);
  useEffect(() => {
    // biome-ignore lint/suspicious/noDocumentCookie: a plain preference, read by the server.
    document.cookie = `${SPACE_COOKIE}=${encodeURIComponent(key)}; path=/; max-age=31536000; samesite=lax`;
  }, [key]);
  return null;
}
