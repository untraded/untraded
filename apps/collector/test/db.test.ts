// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// Against PostgreSQL with the migrations applied (UNTRADED_TEST_DATABASE_URL, set in CI);
// skipped otherwise. Empties the tables it uses.

import { randomBytes } from "node:crypto";
import pg from "pg";
import { afterAll, beforeEach, describe, expect, it } from "vitest";
import { connectionString, PgStore } from "../src/db.js";

const url = process.env.UNTRADED_TEST_DATABASE_URL;
const pool = url ? new pg.Pool({ connectionString: connectionString(url) }) : undefined;
const store = pool ? new PgStore(pool, randomBytes(32)) : undefined;

describe.skipIf(!pool)("PgStore", () => {
  const db = pool as pg.Pool;
  const s = store as PgStore;
  const player = { steamId: "76561198000000001", name: "p1", authCode: "AAAA-11111-BBBB" };

  beforeEach(async () => {
    await db.query("TRUNCATE job, match, app_user CASCADE");
  });
  afterAll(async () => {
    await pool?.end();
  });

  it("adds a followed player with a personal workspace, and reads the source back", async () => {
    const id = await s.addSource({ ...player, shareCode: "CSGO-a" });
    await s.addSource({ ...player, shareCode: "CSGO-b" }); // same user, second source
    const sources = await s.sources();
    expect(sources).toHaveLength(2);
    expect(sources[0]).toEqual({
      id,
      steamId: player.steamId,
      authCode: player.authCode,
      knownShareCode: "CSGO-a",
    });
    const { rows } = await db.query(
      `SELECT count(*)::int AS n FROM workspace w JOIN membership m ON m.workspace_id = w.id
       WHERE w.kind = 'personal'`,
    );
    expect(rows[0].n).toBe(1);
    const secret = await db.query("SELECT secret FROM ingest_source WHERE id = $1", [id]);
    expect(String(secret.rows[0].secret)).not.toContain(player.authCode);
  });

  it("records a match with its source and download job, and advances the chain", async () => {
    await s.addSource({ ...player, shareCode: "CSGO-a" });
    const [source] = await s.sources();
    if (!source) throw new Error("no source");
    const playedAt = new Date("2026-10-19T20:00:00Z");
    await s.recordMatch(source, {
      shareCode: "CSGO-b",
      matchId: "3000000000000000001",
      url: "http://replay/730/1.dem.bz2",
      playedAt,
      endedAt: new Date("2026-10-19T20:40:00Z"),
    });
    expect(await s.hasMatch("3000000000000000001")).toBe(true);
    expect(await s.hasMatch("3000000000000000002")).toBe(false);
    const match = await db.query(
      "SELECT id, status::text, mode::text, played_at, ended_at FROM match",
    );
    expect(match.rows[0]).toMatchObject({
      status: "downloading",
      mode: "premier",
      played_at: playedAt,
      ended_at: new Date("2026-10-19T20:40:00Z"),
    });
    const job = await db.query("SELECT kind, payload FROM job");
    expect(job.rows).toEqual([
      {
        kind: "download",
        payload: { match_id: match.rows[0].id, url: "http://replay/730/1.dem.bz2" },
      },
    ]);
    expect((await s.sources())[0]?.knownShareCode).toBe("CSGO-b");
  });

  it("records a match without a demo as unavailable, with no job", async () => {
    await s.addSource({ ...player, shareCode: "CSGO-a" });
    const [source] = await s.sources();
    if (!source) throw new Error("no source");
    await s.recordMatch(source, {
      shareCode: "CSGO-b",
      matchId: "3000000000000000001",
      url: undefined,
      playedAt: undefined,
      endedAt: undefined,
    });
    const match = await db.query("SELECT status::text FROM match");
    expect(match.rows[0].status).toBe("unavailable");
    expect((await db.query("SELECT 1 FROM job")).rowCount).toBe(0);
  });

  it("records the outcome of a round on the source", async () => {
    await s.addSource({ ...player, shareCode: "CSGO-a" });
    const [source] = await s.sources();
    if (!source) throw new Error("no source");
    await s.sourceDone(source, "412: fresh code needed");
    await s.advance(source, "CSGO-c");
    let row = (await db.query("SELECT last_error, last_success_at, config FROM ingest_source"))
      .rows[0];
    expect(row).toMatchObject({ last_error: "412: fresh code needed", last_success_at: null });
    expect(row.config.known_share_code).toBe("CSGO-c");
    await s.sourceDone(source, undefined);
    row = (await db.query("SELECT last_error, last_success_at FROM ingest_source")).rows[0];
    expect(row.last_error).toBeNull();
    expect(row.last_success_at).not.toBeNull();
  });
});
