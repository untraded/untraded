// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * The service worker's code (`app/sw.js/route.ts`, registered by `components/pwa/pwa-setup.tsx`).
 * Minimal on purpose:
 * - it keeps one file, the offline page (`/offline`), the same for everyone;
 * - it answers page loads only (navigations): from the network, always, and with the offline
 *   page when the network fails. It never stores a response, so no page and no API answer (a
 *   player's data) is ever kept in the browser's cache;
 * - every other request (the API relay, scripts, images, uploads) never reaches it;
 * - a new version takes over at once (`skipWaiting`, `clients.claim`): it holds nothing that
 *   could go stale, so no tab stays on an old worker after a deployment. The browser checks for
 *   one at each visit (`updateViaCache: "none"`, and `Cache-Control: no-cache` on the script).
 *
 * `version` names the cache: a new offline page comes with a new worker that drops the old copy.
 */
export function serviceWorkerSource(version: string): string {
  return `// Untraded's service worker: the offline page, nothing else is cached.
"use strict";
const CACHE = ${JSON.stringify(`untraded-offline-${version}`)};
const OFFLINE = "/offline";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.add(new Request(OFFLINE, { cache: "reload" })))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys()) {
        if (key.startsWith("untraded-") && key !== CACHE) await caches.delete(key);
      }
      // The page request starts while the worker wakes up, not after.
      if (self.registration.navigationPreload) await self.registration.navigationPreload.enable();
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.mode !== "navigate" || request.method !== "GET") return;
  event.respondWith(
    (async () => {
      try {
        const preloaded = await event.preloadResponse;
        if (preloaded) return preloaded;
        return await fetch(request);
      } catch {
        const offline = await caches.match(OFFLINE, { cacheName: CACHE });
        return offline || Response.error();
      }
    })(),
  );
});
`;
}
