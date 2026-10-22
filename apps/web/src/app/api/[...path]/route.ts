// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// `/api/*` is relayed to the API: the web and the API share one origin, so the API's session
// cookie is the web's and a reverse proxy only has to reach the web. Redirects (Steam sign-in)
// and cookies pass through untouched.

import type { NextRequest } from "next/server";
import { internalApiUrl } from "@/lib/api";

export const dynamic = "force-dynamic";

const REQUEST_HEADERS = ["accept", "content-type", "cookie", "user-agent"];
const RESPONSE_HEADERS = ["cache-control", "content-type", "location"];

async function relay(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await params;
  const target = `${internalApiUrl()}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  for (const name of REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const hasBody = !["GET", "HEAD"].includes(request.method);
  const response = await fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : null,
    redirect: "manual",
    cache: "no-store",
  });
  const out = new Headers();
  for (const name of RESPONSE_HEADERS) {
    const value = response.headers.get(name);
    if (value) out.set(name, value);
  }
  for (const cookie of response.headers.getSetCookie()) out.append("set-cookie", cookie);
  // `fetch` decompresses what the API gzipped (a round replay: 40 kB gzipped, 500 kB of JSON),
  // and Next does not compress a route's stream: gzip it again for a browser that takes it.
  const gzipped = /\bgzip\b/.test(response.headers.get("content-encoding") ?? "");
  const accepted = /\bgzip\b/.test(request.headers.get("accept-encoding") ?? "");
  if (gzipped && response.body) {
    out.set("vary", "accept-encoding");
    if (accepted) {
      out.set("content-encoding", "gzip");
      const body = response.body.pipeThrough(new CompressionStream("gzip"));
      return new Response(body, { status: response.status, headers: out });
    }
  }
  return new Response(response.body, { status: response.status, headers: out });
}

export { relay as DELETE, relay as GET, relay as PATCH, relay as POST, relay as PUT };
