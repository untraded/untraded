// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

/** Local, git-ignored state. Contains a secret (the bot refresh token): file mode 600. */
export interface State {
  knownShareCode?: string;
  botRefreshToken?: string;
  processedShareCodes: string[];
}

export async function loadState(path: string): Promise<State> {
  try {
    return JSON.parse(await readFile(path, "utf8")) as State;
  } catch {
    return { processedShareCodes: [] };
  }
}

export async function saveState(path: string, state: State): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(state, null, 2)}\n`, { mode: 0o600 });
  await chmod(path, 0o600);
}
