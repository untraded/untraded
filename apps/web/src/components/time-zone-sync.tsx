// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { isTimeZone, TIME_ZONE_COOKIE } from "@/i18n/time-zone";

/** Sends the browser's time zone to the server in a cookie, and re-renders the page once when it
 * changes, so dates and times show in the player's local time. Renders nothing. */
export function TimeZoneSync({ current }: { current: string }) {
  const router = useRouter();
  useEffect(() => {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (!isTimeZone(zone) || zone === current) return;
    // biome-ignore lint/suspicious/noDocumentCookie: a plain preference, read by the server.
    document.cookie = `${TIME_ZONE_COOKIE}=${encodeURIComponent(zone)}; path=/; max-age=31536000; samesite=lax`;
    router.refresh();
  }, [current, router]);
  return null;
}
