// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

import { createWriteStream } from "node:fs";
import { mkdir, rename, stat } from "node:fs/promises";
import { dirname } from "node:path";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import type { ReadableStream } from "node:stream/web";

export type DownloadResult =
  | { kind: "ok"; bytes: number; seconds: number }
  | { kind: "expired"; status: number } // Valve answers 404/502 once the demo is gone
  | { kind: "error"; status: number };

/** HEAD first (cheap expiry check), then a streamed GET to `destination` via a temp file. */
export async function downloadDemo(url: string, destination: string): Promise<DownloadResult> {
  const head = await fetch(url, { method: "HEAD", signal: AbortSignal.timeout(15_000) });
  if (head.status === 404 || head.status === 502) return { kind: "expired", status: head.status };
  if (!head.ok) return { kind: "error", status: head.status };

  const started = performance.now();
  const response = await fetch(url, { signal: AbortSignal.timeout(10 * 60_000) });
  if (!response.ok || !response.body) return { kind: "error", status: response.status };

  await mkdir(dirname(destination), { recursive: true });
  const partial = `${destination}.part`;
  await pipeline(
    Readable.fromWeb(response.body as ReadableStream<Uint8Array>),
    createWriteStream(partial),
  );
  await rename(partial, destination);
  const { size } = await stat(destination);
  return { kind: "ok", bytes: size, seconds: (performance.now() - started) / 1000 };
}
