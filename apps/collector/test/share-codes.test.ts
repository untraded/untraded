// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { afterEach, describe, expect, it, vi } from "vitest";
import { nextShareCode } from "../src/share-codes.js";

const params = { apiKey: "k", steamId: "765", authCode: "a", knownCode: "CSGO-known" };

function answer(status: number, body: unknown = {}) {
  const fetch = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("nextShareCode", () => {
  it("returns the next code", async () => {
    const fetch = answer(200, { result: { nextcode: "CSGO-next" } });
    expect(await nextShareCode(params)).toEqual({ kind: "next", code: "CSGO-next" });
    const url = new URL(String(fetch.mock.calls[0]?.[0 as never]));
    expect(url.searchParams.get("knowncode")).toBe("CSGO-known");
    expect(url.searchParams.get("steamidkey")).toBe("a");
  });

  it.each([
    [200, { result: { nextcode: "n/a" } }, { kind: "none" }],
    [202, {}, { kind: "none" }],
    [429, {}, { kind: "retry", status: 429 }],
    [503, {}, { kind: "retry", status: 503 }],
  ])("maps HTTP %s", async (status, body, expected) => {
    answer(status, body);
    expect(await nextShareCode(params)).toEqual(expected);
  });

  it.each([403, 412])("stops on %s", async (status) => {
    answer(status);
    expect(await nextShareCode(params)).toMatchObject({ kind: "fatal", status });
  });
});
