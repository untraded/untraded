// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

/**
 * The bot's local state, in COLLECTOR_DATA_DIR (a volume in a container). It holds a secret,
 * the bot's refresh token: file mode 600. The spike's `.state.json` is compatible.
 */
export interface State {
  botRefreshToken?: string;
}

export async function loadState(path: string): Promise<State> {
  try {
    return JSON.parse(await readFile(path, "utf8")) as State;
  } catch {
    return {};
  }
}

export async function saveState(path: string, state: State): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  // Keeps the other fields of an existing file (e.g. the spike's).
  const merged = { ...(await loadState(path)), ...state };
  await writeFile(path, `${JSON.stringify(merged, null, 2)}\n`, { mode: 0o600 });
  await chmod(path, 0o600);
}
