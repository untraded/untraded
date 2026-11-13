// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { decoded, hasNoBody, requestHeaders, responseHeaders, weakEtag } from "../src/lib/relay";

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

  it("knows the encodings fetch decodes", () => {
    expect(decoded(null)).toBe(true);
    expect(decoded("gzip")).toBe(true);
    expect(decoded("GZIP, br")).toBe(true);
    expect(decoded("zstd")).toBe(false);
    expect(decoded("gzip, zstd")).toBe(false);
  });

  it("weakens the ETags it relays", () => {
    expect(weakEtag(ETAG)).toBe(`W/${ETAG}`);
    expect(weakEtag(`W/${ETAG}`)).toBe(`W/${ETAG}`);
  });

  it("relays a replay's caching headers, never an encoding", () => {
    const upstream = new Headers({
      "cache-control": "private, max-age=604800",
      "content-encoding": "gzip",
      "content-length": "40000",
      "content-type": "application/json",
      etag: ETAG,
      vary: "Cookie",
      "x-internal": "no",
    });
    const headers = responseHeaders(upstream);
    expect(headers.get("cache-control")).toBe("private, max-age=604800");
    expect(headers.get("content-type")).toBe("application/json");
    expect(headers.get("etag")).toBe(`W/${ETAG}`);
    expect(headers.get("vary")).toBe("Cookie");
    // `fetch` decoded the body: neither its encoding nor its length is the API's.
    expect(headers.has("content-encoding")).toBe(false);
    expect(headers.has("content-length")).toBe(false);
    expect(headers.has("x-internal")).toBe(false);
  });

  it("relays a 304 without a body", () => {
    const headers = responseHeaders(new Headers({ etag: ETAG, vary: "Cookie" }));
    expect(hasNoBody(304)).toBe(true);
    expect(headers.get("etag")).toBe(`W/${ETAG}`);
    expect(headers.get("vary")).toBe("Cookie");
  });

  it("passes the sign-out's cache clearing and cookies on", () => {
    const upstream = new Headers({ "clear-site-data": '"cache"' });
    upstream.append("set-cookie", "untraded_session=; Max-Age=0; Path=/");
    const headers = responseHeaders(upstream);
    expect(hasNoBody(204)).toBe(true);
    expect(headers.get("clear-site-data")).toBe('"cache"');
    expect(headers.getSetCookie()).toEqual(["untraded_session=; Max-Age=0; Path=/"]);
    expect(headers.has("vary")).toBe(false);
    expect(hasNoBody(200)).toBe(false);
  });
});
