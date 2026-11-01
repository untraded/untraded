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

/** Statuses whose response has no body: the relay neither streams nor gzips them. */
const NULL_BODY = new Set([101, 103, 204, 205, 304]);

export function hasNoBody(status: number): boolean {
  return NULL_BODY.has(status);
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

/** `Vary` values merged, each field name once (case-insensitive, first spelling kept); `*` alone
 * wins. Null when there is nothing to vary on. */
export function mergeVary(...values: (string | null | undefined)[]): string | null {
  const names = new Map<string, string>();
  for (const value of values) {
    for (const name of (value ?? "").split(",")) {
      const trimmed = name.trim();
      if (trimmed === "*") return "*";
      if (trimmed && !names.has(trimmed.toLowerCase())) names.set(trimmed.toLowerCase(), trimmed);
    }
  }
  return names.size ? [...names.values()].join(", ") : null;
}

/** An ETag as the relay passes it on: weak, since `fetch` decodes what the API encoded and the
 * relay may encode it again, so the bytes are not the API's. The API compares `If-None-Match`
 * weakly, so the browser's copy still revalidates. */
export function weakEtag(etag: string): string {
  return etag.startsWith("W/") ? etag : `W/${etag}`;
}

const GZIP = /\bgzip\b/;

/** The headers of the relayed response, and whether its body is gzipped again for the browser.
 * `fetch` decompresses what the API gzipped (a round replay: 40 kB gzipped, 500 kB of JSON), and
 * Next does not compress a route's stream. A 304 has no body: nothing is gzipped, but it keeps
 * the `Vary` of the 200 it revalidates. */
export function responseHeaders(
  upstream: Headers,
  status: number,
  acceptEncoding: string | null,
): { headers: Headers; gzip: boolean } {
  const headers = new Headers();
  for (const name of RESPONSE_HEADERS) {
    const value = upstream.get(name);
    if (value) headers.set(name, name === "etag" ? weakEtag(value) : value);
  }
  for (const cookie of upstream.getSetCookie()) headers.append("set-cookie", cookie);
  const gzipped = GZIP.test(upstream.get("content-encoding") ?? "");
  if (gzipped || status === 304) {
    const vary = mergeVary(upstream.get("vary"), "accept-encoding");
    if (vary) headers.set("vary", vary);
  }
  const gzip = gzipped && !hasNoBody(status) && GZIP.test(acceptEncoding ?? "");
  if (gzip) headers.set("content-encoding", "gzip");
  return { headers, gzip };
}
