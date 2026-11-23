// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { offlineVersion } from "@/lib/offline-page";
import { serviceWorkerSource } from "@/lib/service-worker";

// Served at `/sw.js`, so that its scope is the whole site. Built once per deployment.
export const dynamic = "force-static";

export function GET(): Response {
  return new Response(serviceWorkerSource(offlineVersion()), {
    headers: {
      "Content-Type": "text/javascript; charset=utf-8",
      // Always checked with the server: a new deployment's worker is picked up at the next visit.
      "Cache-Control": "no-cache",
    },
  });
}
