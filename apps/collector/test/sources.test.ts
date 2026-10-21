// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

import { describe, expect, it } from "vitest";
import { formatSources, sourceRef } from "../src/sources.js";

describe("sourceRef", () => {
  it("takes a source id or a SteamID64", () => {
    const id = "0f8fad5b-d9cb-469f-a165-70867728950e";
    expect(sourceRef({ source: id })).toEqual({ id, steamId: undefined });
    expect(sourceRef({ "steam-id": "76561198000000001" })).toEqual({
      id: undefined,
      steamId: "76561198000000001",
    });
  });

  it("refuses no source, and malformed ones, before the database sees them", () => {
    expect(() => sourceRef({})).toThrow(/--source/);
    expect(() => sourceRef({ source: "1; DROP TABLE" })).toThrow(/not a source id/);
    expect(() => sourceRef({ "steam-id": "123" })).toThrow(/not a SteamID64/);
  });
});

describe("formatSources", () => {
  it("lists each source on one line, without its authentication code", () => {
    const lines = formatSources([
      {
        id: "0f8fad5b-d9cb-469f-a165-70867728950e",
        steamId: "76561198000000001",
        name: "p1",
        enabled: false,
        knownShareCode: "CSGO-a",
        lastSuccessAt: new Date("2026-10-21T08:00:00Z"),
        lastError: "403",
        createdAt: new Date("2026-10-20T08:00:00Z"),
      },
    ]);
    expect(lines).toEqual([
      "0f8fad5b-d9cb-469f-a165-70867728950e  76561198000000001  p1  paused  code CSGO-a" +
        "  last 2026-10-21T08:00  error: 403",
    ]);
    expect(formatSources([])).toEqual(["no source"]);
  });
});
