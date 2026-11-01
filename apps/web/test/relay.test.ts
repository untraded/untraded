// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { hasNoBody, mergeVary, requestHeaders, responseHeaders, weakEtag } from "../src/lib/relay";

const ETAG = '"0123abcd"';

describe("relay", () => {
  it("sends the validator of a cached replay on", () => {
    const sent = requestHeaders(
      new Headers({ cookie: "s=1", "if-none-match": `W/${ETAG}`, "x-forwarded-for": "1.2.3.4" }),
    );
    expect(sent.get("if-none-match")).toBe(`W/${ETAG}`);
    expect(sent.get("cookie")).toBe("s=1");
    expect(sent.has("x-forwarded-for")).toBe(false);
  });

  it("merges Vary without losing a name", () => {
    expect(mergeVary("Cookie", "accept-encoding")).toBe("Cookie, accept-encoding");
    expect(mergeVary("Cookie, Accept-Encoding", "accept-encoding")).toBe("Cookie, Accept-Encoding");
    expect(mergeVary(null, "accept-encoding")).toBe("accept-encoding");
    expect(mergeVary("*", "accept-encoding")).toBe("*");
    expect(mergeVary(null, "")).toBeNull();
  });

  it("weakens the ETags it relays", () => {
    expect(weakEtag(ETAG)).toBe(`W/${ETAG}`);
    expect(weakEtag(`W/${ETAG}`)).toBe(`W/${ETAG}`);
  });

  it("gzips a replay again, with its caching headers", () => {
    const upstream = new Headers({
      "cache-control": "private, max-age=604800",
      "content-encoding": "gzip",
      "content-type": "application/json",
      etag: ETAG,
      vary: "Cookie",
      "x-internal": "no",
    });
    const { headers, gzip } = responseHeaders(upstream, 200, "gzip, deflate, br");
    expect(gzip).toBe(true);
    expect(headers.get("content-encoding")).toBe("gzip");
    expect(headers.get("cache-control")).toBe("private, max-age=604800");
    expect(headers.get("etag")).toBe(`W/${ETAG}`);
    expect(headers.get("vary")).toBe("Cookie, accept-encoding");
    expect(headers.has("x-internal")).toBe(false);

    const plain = responseHeaders(upstream, 200, null);
    expect(plain.gzip).toBe(false);
    expect(plain.headers.has("content-encoding")).toBe(false);
    expect(plain.headers.get("vary")).toBe("Cookie, accept-encoding");
  });

  it("relays a 304 without a body to gzip, keeping the Vary of the 200", () => {
    const upstream = new Headers({
      "cache-control": "private, max-age=604800",
      etag: ETAG,
      vary: "Cookie",
    });
    const { headers, gzip } = responseHeaders(upstream, 304, "gzip");
    expect(hasNoBody(304)).toBe(true);
    expect(gzip).toBe(false);
    expect(headers.has("content-encoding")).toBe(false);
    expect(headers.get("etag")).toBe(`W/${ETAG}`);
    expect(headers.get("vary")).toBe("Cookie, accept-encoding");
  });

  it("passes the sign-out's cache clearing and cookies on", () => {
    const upstream = new Headers({ "clear-site-data": '"cache"' });
    upstream.append("set-cookie", "untraded_session=; Max-Age=0; Path=/");
    const { headers, gzip } = responseHeaders(upstream, 204, null);
    expect(gzip).toBe(false);
    expect(hasNoBody(204)).toBe(true);
    expect(headers.get("clear-site-data")).toBe('"cache"');
    expect(headers.getSetCookie()).toEqual(["untraded_session=; Max-Age=0; Path=/"]);
    expect(headers.has("vary")).toBe(false);
    expect(hasNoBody(200)).toBe(false);
  });
});
