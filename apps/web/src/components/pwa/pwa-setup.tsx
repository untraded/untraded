// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { useEffect } from "react";
// Imported for its listeners too: the browser's install offer is kept from the first moment.
import "@/lib/install";

/**
 * Registers the service worker (`app/sw.js/route.ts`) on every page, signed in or not: it lets
 * the browser install the site and shows a page of its own when offline. Production only: in
 * development nothing is registered, so nothing stands between the dev server and the browser.
 * `updateViaCache: "none"` makes the browser fetch the worker afresh at every check, so a new
 * deployment's worker takes over at the next visit.
 */
export function PwaSetup() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).catch(() => {
      // Not served over HTTPS, or blocked by the browser: the site works the same without it.
    });
  }, []);
  return null;
}
