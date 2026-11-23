// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { offlineHtml } from "@/lib/offline-page";

// The same file for everyone, built once: the service worker keeps it for when the network is gone.
export const dynamic = "force-static";

export function GET(): Response {
  return new Response(offlineHtml(), {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-cache",
      "X-Robots-Tag": "noindex",
    },
  });
}
