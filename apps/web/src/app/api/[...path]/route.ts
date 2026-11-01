// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// `/api/*` is relayed to the API: the web and the API share one origin, so the API's session
// cookie is the web's and a reverse proxy only has to reach the web. Redirects (Steam sign-in)
// and cookies pass through untouched. Bodies are streamed, never read whole: a demo a player
// sends (`POST /api/uploads`) weighs up to 400 MB.

import type { NextRequest } from "next/server";
import { internalApiUrl } from "@/lib/api";
import { hasNoBody, requestHeaders, responseHeaders } from "@/lib/relay";

export const dynamic = "force-dynamic";

async function relay(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await params;
  const target = `${internalApiUrl()}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = requestHeaders(request.headers);
  const hasBody = !["GET", "HEAD"].includes(request.method);
  let response: Response;
  try {
    response = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? request.body : null,
      // A stream body must say so (Node's fetch): it is sent as it arrives.
      duplex: "half",
      redirect: "manual",
      cache: "no-store",
    } as RequestInit);
  } catch {
    // The API is down, or answered and closed while the body was still coming (an upload it
    // refused at once): the site checks `GET /api/uploads` first for that.
    return Response.json({ detail: "the API did not answer" }, { status: 502 });
  }
  const { headers: out, gzip } = responseHeaders(
    response.headers,
    response.status,
    request.headers.get("accept-encoding"),
  );
  // A 304 (a replay revalidated) or a 204 has no body: nothing to stream, nor to gzip.
  if (hasNoBody(response.status) || !response.body) {
    return new Response(null, { status: response.status, headers: out });
  }
  const body = gzip ? response.body.pipeThrough(new CompressionStream("gzip")) : response.body;
  return new Response(body, { status: response.status, headers: out });
}

export { relay as DELETE, relay as GET, relay as PATCH, relay as POST, relay as PUT };
