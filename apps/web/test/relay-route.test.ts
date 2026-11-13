// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The `/api/*` relay end to end, as far as a test without a build goes: an API that gzips its
// answers as the real one does, the route handler, and Next's own `sendResponse`, which writes a
// route's `Response` to the Node response (and since Next 16.4.5 drops its `Content-Encoding`:
// the 2D viewer then received a gzipped body it could not read). A client reads what arrives.
// Not covered: Next's router (`next start`), its `compression` middleware, a reverse proxy.

import { createServer, get, type IncomingMessage, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { gunzipSync, gzipSync } from "node:zlib";
import { NodeNextResponse } from "next/dist/server/base-http/node";
import { sendResponse } from "next/dist/server/send-response";
import { NextRequest } from "next/server";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { readReplay, replayPath } from "../src/lib/replay";

const REPLAY = {
  version: 2,
  round: 7,
  map: "de_nuke",
  ticks: Array.from({ length: 500 }, (_, i) => i),
};
const ETAG = '"r7"';

/** The API: a replay gzipped with its ETag (304 when it matches), a sign-in redirect with a
 * cookie, a missing replay. */
function api(): Server {
  return createServer((request, response) => {
    if (request.url?.startsWith("/matches/m/rounds/7/replay")) {
      if (request.headers["if-none-match"]?.includes(ETAG)) {
        response.writeHead(304, { etag: ETAG, "cache-control": "private, max-age=86400" });
        return response.end();
      }
      const body = gzipSync(JSON.stringify(REPLAY));
      response.writeHead(200, {
        "content-type": "application/json",
        "content-encoding": "gzip",
        "content-length": body.length,
        "cache-control": "private, max-age=86400",
        etag: ETAG,
      });
      return response.end(body);
    }
    if (request.url === "/zstd") {
      response.writeHead(200, { "content-type": "application/json", "content-encoding": "zstd" });
      return response.end("not really zstd");
    }
    if (request.url === "/auth/demo") {
      response.writeHead(303, {
        location: "http://web.test/",
        "set-cookie": "untraded_session=demo; Path=/; HttpOnly",
      });
      return response.end();
    }
    response.writeHead(404, { "content-type": "application/json" });
    response.end(JSON.stringify({ detail: "no such replay" }));
  });
}

/** The web: each request goes through the route handler, then Next's `sendResponse`. */
function web(relay: (request: NextRequest, context: unknown) => Promise<Response>): Server {
  return createServer(async (request, response) => {
    const url = new URL(request.url ?? "/", "http://web.test");
    const path = url.pathname.replace(/^\/api\//, "").split("/");
    const headers = new Headers();
    for (const [name, value] of Object.entries(request.headers)) {
      if (typeof value === "string") headers.set(name, value);
    }
    try {
      const answer = await relay(new NextRequest(url, { method: request.method, headers }), {
        params: Promise.resolve({ path }),
      });
      await sendResponse(request as never, new NodeNextResponse(response), answer);
    } catch (error) {
      // A failure fails the test at once rather than leaving the request hanging.
      response.writeHead(500).end(String(error));
    }
  });
}

function listen(server: Server): Promise<string> {
  return new Promise((resolve) =>
    server.listen(0, "127.0.0.1", () => {
      resolve(`http://127.0.0.1:${(server.address() as AddressInfo).port}`);
    }),
  );
}

/** A raw request, as a browser that accepts gzip makes it: nothing decoded on the way. */
function raw(
  url: string,
  headers: Record<string, string> = {},
): Promise<{ response: IncomingMessage; body: Buffer }> {
  return new Promise((resolve, reject) => {
    get(
      url,
      { headers: { "accept-encoding": "gzip, deflate, br, zstd", ...headers } },
      (response) => {
        const chunks: Buffer[] = [];
        response.on("data", (chunk: Buffer) => chunks.push(chunk));
        response.on("end", () => resolve({ response, body: Buffer.concat(chunks) }));
      },
    ).on("error", reject);
  });
}

/** The body as a browser reads it: decoded only when the response says it is encoded. */
function asBrowserReadsIt(response: IncomingMessage, body: Buffer): unknown {
  const encoding = response.headers["content-encoding"];
  if (encoding && encoding !== "gzip") throw new Error(`unexpected encoding ${encoding}`);
  return JSON.parse((encoding === "gzip" ? gunzipSync(body) : body).toString("utf8"));
}

describe("relay route, through Next's sendResponse", () => {
  const servers: Server[] = [];
  const apiUrl = process.env.UNTRADED_API_INTERNAL_URL;
  let base = "";

  beforeAll(async () => {
    const upstream = api();
    servers.push(upstream);
    process.env.UNTRADED_API_INTERNAL_URL = await listen(upstream);
    const { GET } = await import("../src/app/api/[...path]/route");
    const site = web(GET as never);
    servers.push(site);
    base = await listen(site);
  });

  afterAll(async () => {
    if (apiUrl === undefined) delete process.env.UNTRADED_API_INTERNAL_URL;
    else process.env.UNTRADED_API_INTERNAL_URL = apiUrl;
    await Promise.all(servers.map((server) => new Promise((done) => server.close(done))));
  });

  it("sends a replay the browser can read", async () => {
    const { response, body } = await raw(`${base}/api/matches/m/rounds/7/replay?v=2`);
    expect(response.statusCode).toBe(200);
    expect(response.headers["content-type"]).toBe("application/json");
    expect(response.headers.etag).toBe(`W/${ETAG}`);
    expect(response.headers["cache-control"]).toBe("private, max-age=86400");
    expect(asBrowserReadsIt(response, body)).toEqual(REPLAY);
  });

  it("gives the viewer its replay", async () => {
    const answer = await fetch(`${base}/api${replayPath("m", 7)}`);
    expect(await readReplay(answer)).toEqual(REPLAY);
  });

  it("revalidates a cached replay with a 304", async () => {
    const { response, body } = await raw(`${base}/api/matches/m/rounds/7/replay?v=2`, {
      "if-none-match": `W/${ETAG}`,
    });
    expect(response.statusCode).toBe(304);
    expect(body.length).toBe(0);
    expect(response.headers.etag).toBe(`W/${ETAG}`);
  });

  it("passes a redirect and its cookie on", async () => {
    const { response } = await raw(`${base}/api/auth/demo`);
    expect(response.statusCode).toBe(303);
    expect(response.headers.location).toBe("http://web.test/");
    expect(response.headers["set-cookie"]).toEqual(["untraded_session=demo; Path=/; HttpOnly"]);
  });

  it("refuses an encoding fetch does not decode, rather than send it undeclared", async () => {
    const { response } = await raw(`${base}/api/zstd`);
    expect(response.statusCode).toBe(502);
  });

  it("says a missing replay is missing", async () => {
    expect(await readReplay(await fetch(`${base}/api/matches/m/rounds/8/replay?v=2`))).toBe(
      "missing",
    );
  });
});

describe("replayPath", () => {
  it("never reuses the address of the copies browsers cached broken", () => {
    // Next 16.4.5 sent these gzipped without `Content-Encoding`; a 304 would keep them for good.
    expect(replayPath("m", 7)).not.toBe("/matches/m/rounds/7/replay?v=2");
    expect(replayPath("m", 7)).toMatch(/^\/matches\/m\/rounds\/7\/replay\?v=2&/);
  });
});

describe("readReplay", () => {
  const json = (body: BodyInit, status = 200) =>
    new Response(body, { status, headers: { "content-type": "application/json" } });

  it("fails on a gzipped body sent without its Content-Encoding, never hangs", async () => {
    expect(await readReplay(json(gzipSync(JSON.stringify(REPLAY))))).toBe("failed");
  });

  it("fails on another format version or an error", async () => {
    expect(await readReplay(json(JSON.stringify({ ...REPLAY, version: 1 })))).toBe("failed");
    expect(await readReplay(json("null"))).toBe("failed");
    expect(await readReplay(json("{}", 502))).toBe("failed");
    expect(await readReplay(json("{}", 404))).toBe("missing");
  });
});
