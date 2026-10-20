// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { encodeMatch } from "csgo-sharecode";
import type { MatchInfo } from "globaloffensive";
import { describe, expect, it } from "vitest";
import { collect, type Deps, foundMatch } from "../src/collect.js";
import type { FoundMatch, Source, Store } from "../src/db.js";
import type { NextCodeResult } from "../src/share-codes.js";

const code = (n: number) =>
  encodeMatch({
    matchId: 3_000_000_000_000_000_000n + BigInt(n),
    reservationId: 3_712_345_678_901_234_999n,
    tvPort: 1,
  });
const matchId = (n: number) => (3_000_000_000_000_000_000n + BigInt(n)).toString();

class FakeStore implements Store {
  recorded: FoundMatch[] = [];
  known = new Set<string>();
  done: (string | undefined)[] = [];
  constructor(readonly list: Source[]) {}
  async sources() {
    return this.list;
  }
  async hasMatch(id: string) {
    return this.known.has(id);
  }
  async recordMatch(source: Source, match: FoundMatch) {
    this.recorded.push(match);
    this.known.add(match.matchId);
    source.knownShareCode = match.shareCode;
  }
  async advance(source: Source, shareCode: string) {
    source.knownShareCode = shareCode;
  }
  async sourceDone(_: Source, error: string | undefined) {
    this.done.push(error);
  }
}

function setup(options: {
  chain: number[];
  end?: NextCodeResult;
  gcFails?: number;
  noDemo?: number;
}) {
  const source: Source = { id: "s1", steamId: "765", authCode: "x", knownShareCode: code(0) };
  const store = new FakeStore([source]);
  let gcOpened = 0;
  const deps: Deps = {
    store,
    async nextShareCode({ knownCode }) {
      const index = options.chain.findIndex((n) => code(n) === knownCode);
      const next = options.chain[index + 1];
      if (next !== undefined) return { kind: "next", code: code(next) };
      return options.end ?? { kind: "none" };
    },
    async gc() {
      gcOpened++;
      return {
        async requestMatch(shareCode: string): Promise<MatchInfo> {
          const n = options.chain.find((m) => code(m) === shareCode);
          if (n === options.gcFails) throw new Error("GC timeout");
          return {
            matchtime: 1_760_000_000,
            roundstatsall: [
              {},
              { map: n === options.noDemo ? "" : `http://replay/730/${n}.dem.bz2` },
            ],
          };
        },
      };
    },
    sleep: async () => undefined,
    log: () => undefined,
  };
  return { source, store, deps, gcOpened: () => gcOpened };
}

describe("collect", () => {
  it("records each new match in chain order and advances the known code", async () => {
    const { source, store, deps } = setup({ chain: [0, 1, 2, 3] });
    const [report] = await collect(deps, 20);
    expect(report).toEqual({ source: "s1", recorded: 3 });
    expect(store.recorded.map((m) => m.matchId)).toEqual([1, 2, 3].map(matchId));
    expect(store.recorded[0]?.url).toBe("http://replay/730/1.dem.bz2");
    expect(store.recorded[0]?.playedAt).toEqual(new Date(1_760_000_000_000));
    expect(source.knownShareCode).toBe(code(3));
    expect(store.done).toEqual([undefined]);
  });

  it("stops at the per-round limit", async () => {
    const { store, deps } = setup({ chain: [0, 1, 2, 3] });
    await collect(deps, 2);
    expect(store.recorded).toHaveLength(2);
  });

  it("skips a match another player already brought, without asking the GC", async () => {
    const { source, store, deps, gcOpened } = setup({ chain: [0, 1] });
    store.known.add(matchId(1));
    await collect(deps, 20);
    expect(store.recorded).toEqual([]);
    expect(source.knownShareCode).toBe(code(1));
    expect(gcOpened()).toBe(0);
  });

  it("keeps the known code before a match the GC failed on", async () => {
    const { source, store, deps } = setup({ chain: [0, 1, 2, 3], gcFails: 2 });
    const [report] = await collect(deps, 20);
    expect(report?.recorded).toBe(1);
    expect(report?.error).toContain("GC timeout");
    expect(source.knownShareCode).toBe(code(1));
    expect(store.done).toEqual([report?.error]);
  });

  it("records a match without a demo", async () => {
    const { store, deps } = setup({ chain: [0, 1], noDemo: 1 });
    await collect(deps, 20);
    expect(store.recorded[0]?.url).toBeUndefined();
  });

  it("reports a broken chain (412) after recording what came before", async () => {
    const end: NextCodeResult = { kind: "fatal", status: 412, reason: "fresh code needed" };
    const { store, deps } = setup({ chain: [0, 1], end });
    const [report] = await collect(deps, 20);
    expect(report?.recorded).toBe(1);
    expect(report?.error).toBe("412: fresh code needed");
    expect(store.done).toEqual(["412: fresh code needed"]);
  });

  it("needs a known share code", async () => {
    const { source, deps } = setup({ chain: [0] });
    source.knownShareCode = undefined;
    const [report] = await collect(deps, 20);
    expect(report?.error).toMatch(/no known share code/);
  });
});

describe("foundMatch", () => {
  it("reads the demo URL on the last round", () => {
    const match = foundMatch(code(7), { roundstatsall: [{ map: "old" }, { map: "u" }] });
    expect(match).toEqual({
      shareCode: code(7),
      matchId: matchId(7),
      url: "u",
      playedAt: undefined,
    });
  });
});
