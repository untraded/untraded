// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The source commands' arguments and listing.

import type { SourceInfo, SourceRef } from "./db.js";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const STEAM_ID = /^7656119\d{10}$/;

/** `--source <id>` or `--steam-id <SteamID64>`, checked before it reaches the database. */
export function sourceRef(values: { source?: string; "steam-id"?: string }): SourceRef {
  const id = values.source;
  const steamId = values["steam-id"];
  if (!id && !steamId) throw new Error("name the source: --source <id> or --steam-id <SteamID64>");
  if (id && !UUID.test(id)) throw new Error(`not a source id: ${id}`);
  if (steamId && !STEAM_ID.test(steamId)) throw new Error(`not a SteamID64: ${steamId}`);
  return { id, steamId };
}

export function formatSources(sources: SourceInfo[]): string[] {
  if (sources.length === 0) return ["no source"];
  return sources.map((s) => {
    const state = s.enabled ? "active" : "paused";
    const last = s.lastSuccessAt ? s.lastSuccessAt.toISOString().slice(0, 16) : "never";
    const error = s.lastError ? `  error: ${s.lastError}` : "";
    return `${s.id}  ${s.steamId}  ${s.name}  ${state}  code ${s.knownShareCode ?? "-"}  last ${last}${error}`;
  });
}
