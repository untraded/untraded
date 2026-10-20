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
  return new Response(response.body, { status: response.status, headers: out });
}

export { relay as DELETE, relay as GET, relay as PATCH, relay as POST, relay as PUT };
