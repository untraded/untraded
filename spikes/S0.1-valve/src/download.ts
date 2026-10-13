// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

import { createWriteStream } from "node:fs";
import { mkdir, rename, stat } from "node:fs/promises";
import { dirname } from "node:path";

// Valve replay servers throttle each connection (~50-170 KB/s observed) and drop it every few
// MB ("terminated"), so we resume with HTTP Range requests and keep going while bytes arrive.
const MAX_ATTEMPTS_WITHOUT_PROGRESS = 5;
const STALL_TIMEOUT_MS = 60_000;
const RETRY_DELAY_MS = 5_000;

export type DownloadResult =
  | {
      kind: "ok";
      bytes: number;
      seconds: number;
      attempts: number;
      resumed: boolean;
      expiresAt: string | undefined; // GCS custom time on the object: when Valve deletes the demo
    }
  | { kind: "expired"; status: number } // Valve answers 404/502 once the demo is gone
  | { kind: "error"; status: number; attempts: number; bytes: number; lastError?: string };

const sleep = (ms: number) => new Promise((done) => setTimeout(done, ms));

async function sizeOf(path: string): Promise<number> {
  try {
    return (await stat(path)).size;
  } catch {
    return 0;
  }
}

/** Streams the response body to `path` (appending when `append`), aborting if no data arrives for a while. */
async function writeBody(
  response: Response,
  path: string,
  append: boolean,
  controller: AbortController,
) {
  if (!response.body) throw new Error("empty response body");
  const out = createWriteStream(path, { flags: append ? "a" : "w" });
  let stall = setTimeout(() => controller.abort(new Error("download stalled")), STALL_TIMEOUT_MS);
  try {
    for await (const chunk of response.body) {
      clearTimeout(stall);
      stall = setTimeout(() => controller.abort(new Error("download stalled")), STALL_TIMEOUT_MS);
      if (!out.write(chunk)) await new Promise<void>((done) => out.once("drain", () => done()));
    }
  } finally {
    clearTimeout(stall);
    await new Promise<void>((done, fail) =>
      out.end((error?: Error | null) => (error ? fail(error) : done())),
    );
  }
}

/**
 * HEAD first (cheap expiry check), then a streamed GET to `destination` via a `.part` file.
 * Interrupted transfers are resumed with `Range` (also across runs, since the `.part` file stays).
 */
export async function downloadDemo(url: string, destination: string): Promise<DownloadResult> {
  const head = await fetch(url, { method: "HEAD", signal: AbortSignal.timeout(15_000) });
  if (head.status === 404 || head.status === 502) return { kind: "expired", status: head.status };
  if (!head.ok) return { kind: "error", status: head.status, attempts: 0, bytes: 0 };
  const expected = Number(head.headers.get("content-length") ?? Number.NaN);

  await mkdir(dirname(destination), { recursive: true });
  const partial = `${destination}.part`;
  const started = performance.now();
  const resumed = (await sizeOf(partial)) > 0;
  const expiresAt = head.headers.get("x-goog-custom-time") ?? undefined;
  let lastError: string | undefined;
  let status = 0;
  let attempts = 0;
  let withoutProgress = 0;

  while (true) {
    attempts++;
    let have = await sizeOf(partial);
    if (have > 0 && have === expected) break;
    if (have > expected) have = 0; // stale or corrupt partial file: start over

    const controller = new AbortController();
    try {
      const response = await fetch(url, {
        headers: have > 0 ? { Range: `bytes=${have}-` } : {},
        signal: controller.signal,
      });
      status = response.status;
      if (response.status === 404 || response.status === 502) return { kind: "expired", status };
      if (response.status !== 200 && response.status !== 206) {
        lastError = `HTTP ${response.status}`;
      } else {
        // 200 means the server ignored Range (or we start over): rewrite from the start.
        await writeBody(response, partial, response.status === 206, controller);
        if (Number.isNaN(expected) || (await sizeOf(partial)) === expected) break;
        lastError = "short read";
      }
    } catch (error) {
      lastError = String(error);
    }
    const now = await sizeOf(partial);
    withoutProgress = now > have ? 0 : withoutProgress + 1;
    console.error(`  attempt ${attempts} interrupted at ${now}/${expected} bytes: ${lastError}`);
    if (withoutProgress >= MAX_ATTEMPTS_WITHOUT_PROGRESS) {
      return { kind: "error", status, attempts, bytes: now, lastError };
    }
    await sleep(RETRY_DELAY_MS);
  }

  await rename(partial, destination);
  const bytes = await sizeOf(destination);
  const seconds = (performance.now() - started) / 1000;
  return { kind: "ok", bytes, seconds, attempts, resumed, expiresAt };
}
