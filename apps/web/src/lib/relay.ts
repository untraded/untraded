// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// Which headers the `/api/*` relay (`app/api/[...path]/route.ts`) passes on, and how. Pure, so
// tested without a server. In production a reverse proxy may reach the API directly: the relay
// must answer as the API does, caching headers included.

// `content-length` too: the body is streamed, and the API refuses a too large upload from it
// before reading anything. `if-none-match`: a round replay revalidates with its ETag (304).
export const REQUEST_HEADERS = [
  "accept",
  "content-length",
  "content-type",
  "cookie",
  "if-none-match",
  "user-agent",
];
// `clear-site-data`: sign-out and erasure clear the browser's cache of the site.
export const RESPONSE_HEADERS = [
  "cache-control",
  "clear-site-data",
  "content-type",
  "etag",
  "location",
  "vary",
];

/** Statuses whose response has no body: the relay does not stream them. */
const NULL_BODY = new Set([101, 103, 204, 205, 304]);

export function hasNoBody(status: number): boolean {
  return NULL_BODY.has(status);
}

const DECODED = new Set(["", "identity", "gzip", "x-gzip", "deflate", "br"]);

/** Whether `fetch` hands the body over decoded: no encoding, or one it decodes. */
export function decoded(contentEncoding: string | null): boolean {
  return (contentEncoding ?? "")
    .split(",")
    .every((coding) => DECODED.has(coding.trim().toLowerCase()));
}

/** The headers of the request sent on to the API. */
export function requestHeaders(incoming: Headers): Headers {
  const headers = new Headers();
  for (const name of REQUEST_HEADERS) {
    const value = incoming.get(name);
    if (value) headers.set(name, value);
  }
  return headers;
}

/** An ETag as the relay passes it on: weak, since `fetch` decodes what the API encoded, so the
 * bytes are not the API's. The API compares `If-None-Match`
 * weakly, so the browser's copy still revalidates. */
export function weakEtag(etag: string): string {
  return etag.startsWith("W/") ? etag : `W/${etag}`;
}

/** The headers of the relayed response. Its body is sent as `fetch` gives it: decoded. The API
 * gzips a round replay (40 kB gzipped, about 500 kB of JSON), `fetch` decompresses it, and the
 * relay cannot gzip it again: since 16.4.5, Next drops `Content-Encoding` (and `Content-Length`,
 * `Transfer-Encoding`) from every route's `Response`, so a gzipped body would reach the browser
 * undeclared and unreadable; and Next's own compression skips a route's response (it sets the
 * route's headers so that `compression` cannot read their type). A reverse proxy in front
 * compresses it (`docs/self-hosting.md`). */
export function responseHeaders(upstream: Headers): Headers {
  const headers = new Headers();
  for (const name of RESPONSE_HEADERS) {
    const value = upstream.get(name);
    if (value) headers.set(name, name === "etag" ? weakEtag(value) : value);
  }
  for (const cookie of upstream.getSetCookie()) headers.append("set-cookie", cookie);
  return headers;
}
