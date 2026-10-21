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

  it("lists, finds, changes, pauses and removes a source", async () => {
    const id = await s.addSource({ ...player, shareCode: "CSGO-a" });
    await db.query("UPDATE ingest_source SET last_error = '403' WHERE id = $1", [id]);
    const [listed] = await s.listSources();
    expect(listed).toMatchObject({ id, steamId: player.steamId, name: "p1", enabled: true });
    expect(JSON.stringify(listed)).not.toContain(player.authCode);
    expect(await s.findSource({ steamId: player.steamId })).toBe(id);
    expect(await s.findSource({ id })).toBe(id);

    // A new code clears the error, and the collector reads the new values.
    await s.updateSource(id, { shareCode: "CSGO-z", authCode: "CCCC-22222-DDDD" });
    expect(await s.sources()).toEqual([
      { id, steamId: player.steamId, authCode: "CCCC-22222-DDDD", knownShareCode: "CSGO-z" },
    ]);
    expect((await s.listSources())[0]?.lastError).toBeUndefined();

    await s.updateSource(id, { enabled: false });
    expect(await s.sources()).toEqual([]);
    await s.updateSource(id, { enabled: true });
    expect(await s.sources()).toHaveLength(1);

    // A second source makes the SteamID ambiguous.
    const other = await s.addSource({ ...player, shareCode: "CSGO-b" });
    await expect(s.findSource({ steamId: player.steamId })).rejects.toThrow(/several sources/);

    // Removing keeps the player's matches, without their source.
    const [source] = await s.sources();
    if (!source) throw new Error("no source");
    await s.recordMatch(source, {
      shareCode: "CSGO-y",
      matchId: "3000000000000000009",
      url: "http://replay/730/9.dem.bz2",
      playedAt: undefined,
      endedAt: undefined,
    });
    await s.removeSource(id);
    await s.removeSource(other);
    expect(await s.listSources()).toEqual([]);
    const kept = await db.query(
      "SELECT source_id FROM match_source WHERE external_id = '3000000000000000009'",
    );
    expect(kept.rows).toEqual([{ source_id: null }]);
    await expect(s.removeSource(id)).rejects.toThrow(/no such source/);
    await expect(s.findSource({ id })).rejects.toThrow(/no such source/);
  });

  it("records consent with the source, then each change as a new row", async () => {
    await s.addSource({
      ...player,
      shareCode: "CSGO-a",
      consent: { textVersion: "1", analysis: true, researchCorpus: false },
    });
    expect((await s.listSources())[0]?.consent).toEqual({
      textVersion: "1",
      analysis: true,
      researchCorpus: false,
    });

    await s.recordConsent(player.steamId, {
      textVersion: "2",
      analysis: true,
      researchCorpus: true,
    });
    expect((await s.listSources())[0]?.consent?.researchCorpus).toBe(true);

    // Withdrawing keeps the version, and never leaves box 2 ticked.
    await s.recordConsent(player.steamId, {
      textVersion: undefined,
      analysis: false,
      researchCorpus: true,
    });
    expect((await s.listSources())[0]?.consent).toEqual({
      textVersion: "2",
      analysis: false,
      researchCorpus: false,
    });
    const history = await db.query("SELECT text_version FROM consent ORDER BY id");
    expect(history.rows.map((r) => r.text_version)).toEqual(["1", "2", "2"]);

    await expect(
      s.recordConsent("76561198000000099", {
        textVersion: "1",
        analysis: true,
        researchCorpus: false,
      }),
    ).rejects.toThrow(/no such player/);
  });

  it("refuses a withdrawal with no version to keep", async () => {
    await s.addSource({ ...player, shareCode: "CSGO-a" });
    await expect(
      s.recordConsent(player.steamId, {
        textVersion: undefined,
        analysis: false,
        researchCorpus: false,
      }),
    ).rejects.toThrow(/--text-version/);
  });
});
