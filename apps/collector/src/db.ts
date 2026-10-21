// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// What the collector reads and writes in the database (ADR 0011). It connects with the
// services role, which bypasses row-level security, like the worker.

import { randomUUID } from "node:crypto";
import type pg from "pg";
import { decrypt, encrypt } from "./secrets.js";

/** A player whose Valve matches the bot follows (`ingest_source` of kind `valve_bot`). */
export interface Source {
  id: string;
  steamId: string;
  authCode: string;
  knownShareCode: string | undefined;
}

/** A source as `sources` lists it: everything but its authentication code. */
export interface SourceInfo {
  id: string;
  steamId: string;
  name: string;
  enabled: boolean;
  knownShareCode: string | undefined;
  lastSuccessAt: Date | undefined;
  lastError: string | undefined;
  createdAt: Date;
  /** The player's current consent, if one was recorded. */
  consent: Consent | undefined;
}

/** What a player agreed to (`consent`): the text's version and its two boxes. */
export interface Consent {
  /** Withdrawing without naming a version keeps the version of the current consent. */
  textVersion: string;
  /** Box 1: collect and analyse their matches. Required to follow them. */
  analysis: boolean;
  /** Box 2: keep their raw demos in the research corpus. */
  researchCorpus: boolean;
}

/** What `update-source` can change. A new code clears the last error: the next round tries it. */
export interface SourceChange {
  shareCode?: string | undefined;
  authCode?: string | undefined;
  enabled?: boolean | undefined;
}

/** A source named by its id, or by its player's SteamID64. */
export interface SourceRef {
  id?: string | undefined;
  steamId?: string | undefined;
}

export interface FoundMatch {
  shareCode: string;
  /** Valve match id, the `external_id` of the match source. */
  matchId: string;
  /** Demo URL from the Game Coordinator; missing when Valve has no demo. */
  url: string | undefined;
  playedAt: Date | undefined;
  /** When the match ended: play sessions are cut on the time between two matches. */
  endedAt: Date | undefined;
}

export interface Store {
  sources(): Promise<Source[]>;
  hasMatch(matchId: string): Promise<boolean>;
  /** Records a new match, its source and its `download` job, and advances the chain. */
  recordMatch(source: Source, match: FoundMatch): Promise<void>;
  /** Moves the source's known share code forward (a match already known). */
  advance(source: Source, shareCode: string): Promise<void>;
  sourceDone(source: Source, error: string | undefined): Promise<void>;
}

/** `postgresql+psycopg://` (the Python services' form) is accepted too. */
export function connectionString(url: string | undefined): string {
  return (url ?? "postgresql://untraded:untraded@localhost:5432/untraded").replace(
    /^postgresql\+psycopg:/,
    "postgresql:",
  );
}

interface SourceRow {
  id: string;
  steam_id: string;
  config: { known_share_code?: string };
  secret: Buffer | null;
}

export class PgStore implements Store {
  constructor(
    private readonly pool: pg.Pool,
    private readonly key: Buffer,
  ) {}

  async sources(): Promise<Source[]> {
    const { rows } = await this.pool.query<SourceRow>(
      `SELECT s.id, u.steam_id::text AS steam_id, s.config, s.secret
       FROM ingest_source s JOIN app_user u ON u.id = s.user_id
       WHERE s.kind = 'valve_bot' AND s.enabled AND u.deleted_at IS NULL
       ORDER BY s.created_at`,
    );
    return rows.flatMap((row) =>
      row.secret
        ? [
            {
              id: row.id,
              steamId: row.steam_id,
              authCode: decrypt(this.key, row.secret, row.id),
              knownShareCode: row.config.known_share_code,
            },
          ]
        : [],
    );
  }

  async hasMatch(matchId: string): Promise<boolean> {
    const { rowCount } = await this.pool.query(
      "SELECT 1 FROM match_source WHERE kind = 'valve_bot' AND external_id = $1",
      [matchId],
    );
    return (rowCount ?? 0) > 0;
  }

  async recordMatch(source: Source, match: FoundMatch): Promise<void> {
    await this.transaction(async (client) => {
      // The share-code chain also holds Competitive and Wingman matches: the mode is only
      // known from the demo, so the worker checks it when parsing.
      const { rows } = await client.query<{ id: string }>(
        `INSERT INTO match (mode, played_at, ended_at, status, error)
         VALUES ('premier', $1, $2, $3, $4) RETURNING id`,
        [
          match.playedAt ?? null,
          match.endedAt ?? null,
          match.url ? "downloading" : "unavailable",
          match.url ? null : "Valve has no demo for this match",
        ],
      );
      const id = rows[0]?.id;
      await client.query(
        `INSERT INTO match_source (match_id, kind, external_id, source_id)
         VALUES ($1, 'valve_bot', $2, $3)`,
        [id, match.matchId, source.id],
      );
      if (match.url) {
        await client.query("INSERT INTO job (kind, payload) VALUES ('download', $1)", [
          { match_id: id, url: match.url },
        ]);
      }
      await this.setKnownCode(client, source, match.shareCode);
    });
    source.knownShareCode = match.shareCode;
  }

  async advance(source: Source, shareCode: string): Promise<void> {
    await this.setKnownCode(this.pool, source, shareCode);
    source.knownShareCode = shareCode;
  }

  async sourceDone(source: Source, error: string | undefined): Promise<void> {
    await this.pool.query(
      error
        ? "UPDATE ingest_source SET last_error = $2 WHERE id = $1"
        : "UPDATE ingest_source SET last_error = NULL, last_success_at = now() WHERE id = $1",
      error ? [source.id, error] : [source.id],
    );
  }

  /** Every bot source, oldest first, with its player's name. */
  async listSources(): Promise<SourceInfo[]> {
    const { rows } = await this.pool.query<{
      id: string;
      steam_id: string;
      display_name: string;
      enabled: boolean;
      config: { known_share_code?: string };
      last_success_at: Date | null;
      last_error: string | null;
      created_at: Date;
      text_version: string | null;
      analysis: boolean | null;
      research_corpus: boolean | null;
    }>(
      `SELECT s.id, u.steam_id::text AS steam_id, u.display_name, s.enabled, s.config,
              s.last_success_at, s.last_error, s.created_at,
              c.text_version, c.analysis, c.research_corpus
       FROM ingest_source s JOIN app_user u ON u.id = s.user_id
       LEFT JOIN consent_current c ON c.user_id = u.id
       WHERE s.kind = 'valve_bot'
       ORDER BY s.created_at`,
    );
    return rows.map((row) => ({
      id: row.id,
      steamId: row.steam_id,
      name: row.display_name,
      enabled: row.enabled,
      knownShareCode: row.config.known_share_code,
      lastSuccessAt: row.last_success_at ?? undefined,
      lastError: row.last_error ?? undefined,
      createdAt: row.created_at,
      consent:
        row.text_version === null
          ? undefined
          : {
              textVersion: row.text_version,
              analysis: row.analysis === true,
              researchCorpus: row.research_corpus === true,
            },
    }));
  }

  /**
   * The source a command acts on: by its id, or by its player's SteamID64 when that player has
   * a single bot source.
   */
  async findSource(ref: SourceRef): Promise<string> {
    const { rows } = await this.pool.query<{ id: string }>(
      `SELECT s.id FROM ingest_source s JOIN app_user u ON u.id = s.user_id
       WHERE s.kind = 'valve_bot' AND ($1::uuid IS NULL OR s.id = $1::uuid)
         AND ($2::bigint IS NULL OR u.steam_id = $2::bigint)`,
      [ref.id ?? null, ref.steamId ?? null],
    );
    if (rows.length === 0) throw new Error("no such source");
    if (rows.length > 1) {
      throw new Error(
        `several sources for this player, pick one with --source: ${rows.map((r) => r.id).join(", ")}`,
      );
    }
    return (rows[0] as { id: string }).id;
  }

  async updateSource(id: string, change: SourceChange): Promise<void> {
    const sets: string[] = [];
    const values: unknown[] = [id];
    if (change.shareCode !== undefined) {
      values.push(change.shareCode);
      sets.push(
        `config = jsonb_set(config, '{known_share_code}', to_jsonb($${values.length}::text))`,
      );
    }
    if (change.authCode !== undefined) {
      values.push(encrypt(this.key, change.authCode, id));
      sets.push(`secret = $${values.length}`);
    }
    if (change.shareCode !== undefined || change.authCode !== undefined) {
      sets.push("last_error = NULL");
    }
    if (change.enabled !== undefined) {
      values.push(change.enabled);
      sets.push(`enabled = $${values.length}`);
    }
    if (sets.length === 0) throw new Error("nothing to change");
    const { rowCount } = await this.pool.query(
      `UPDATE ingest_source SET ${sets.join(", ")} WHERE id = $1 AND kind = 'valve_bot'`,
      values,
    );
    if (rowCount === 0) throw new Error("no such source");
  }

  /**
   * Stops following a player for good: the source and its encrypted authentication code are
   * deleted. Their matches, their user and their access to the site stay.
   */
  async removeSource(id: string): Promise<void> {
    const { rowCount } = await this.pool.query(
      "DELETE FROM ingest_source WHERE id = $1 AND kind = 'valve_bot'",
      [id],
    );
    if (rowCount === 0) throw new Error("no such source");
  }

  /**
   * Registers a player followed by the bot: their user (with a personal workspace, so they
   * see their matches) and the source. Returns the source id.
   */
  async addSource(params: {
    steamId: string;
    name: string;
    authCode: string;
    shareCode: string;
    /** Recorded with the source, in the same transaction. */
    consent?: Consent | undefined;
  }): Promise<string> {
    return this.transaction(async (client) => {
      const user = await client.query<{ id: string }>(
        `INSERT INTO app_user (steam_id, display_name) VALUES ($1, $2)
         ON CONFLICT (steam_id) DO UPDATE SET display_name = app_user.display_name
         RETURNING id`,
        [params.steamId, params.name],
      );
      const userId = user.rows[0]?.id;
      const personal = await client.query(
        "SELECT 1 FROM workspace WHERE kind = 'personal' AND created_by = $1",
        [userId],
      );
      if (personal.rowCount === 0) {
        const workspace = await client.query<{ id: string }>(
          `INSERT INTO workspace (kind, name, slug, created_by)
           VALUES ('personal', $1, $2, $3) RETURNING id`,
          [params.name, `u-${params.steamId}`, userId],
        );
        const workspaceId = workspace.rows[0]?.id;
        const role = await client.query<{ id: string }>(
          `INSERT INTO workspace_role (workspace_id, name, permissions)
           VALUES ($1, 'owner', ARRAY['*']) RETURNING id`,
          [workspaceId],
        );
        await client.query(
          "INSERT INTO membership (workspace_id, user_id, role_id) VALUES ($1, $2, $3)",
          [workspaceId, userId, role.rows[0]?.id],
        );
      }
      const id = randomUUID();
      await client.query(
        `INSERT INTO ingest_source (id, user_id, kind, config, secret)
         VALUES ($1, $2, 'valve_bot', $3, $4)`,
        [
          id,
          userId,
          { known_share_code: params.shareCode },
          encrypt(this.key, params.authCode, id),
        ],
      );
      if (params.consent) await insertConsent(client, userId as string, params.consent);
      return id;
    });
  }

  /**
   * Records a player's consent, as a new row: the previous ones stay, as history. Withdrawing
   * box 1 also withdraws box 2.
   */
  async recordConsent(
    steamId: string,
    consent: Omit<Consent, "textVersion"> & { textVersion: string | undefined },
  ): Promise<void> {
    const { rows } = await this.pool.query<{ id: string }>(
      "SELECT id FROM app_user WHERE steam_id = $1::bigint AND deleted_at IS NULL",
      [steamId],
    );
    const userId = rows[0]?.id;
    if (!userId) throw new Error("no such player: add them first with add-source");
    await insertConsent(this.pool, userId, consent);
  }

  private async setKnownCode(
    client: pg.Pool | pg.PoolClient,
    source: Source,
    shareCode: string,
  ): Promise<void> {
    await client.query(
      `UPDATE ingest_source
       SET config = jsonb_set(config, '{known_share_code}', to_jsonb($2::text))
       WHERE id = $1`,
      [source.id, shareCode],
    );
  }

  private async transaction<T>(work: (client: pg.PoolClient) => Promise<T>): Promise<T> {
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      const result = await work(client);
      await client.query("COMMIT");
      return result;
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }
}

async function insertConsent(
  client: pg.Pool | pg.PoolClient,
  userId: string,
  consent: Omit<Consent, "textVersion"> & { textVersion: string | undefined },
): Promise<void> {
  const { rowCount } = await client.query(
    `INSERT INTO consent (user_id, text_version, analysis, research_corpus, recorded_by)
     SELECT $1, v, $3, $4, 'collector cli'
     FROM (SELECT coalesce($2::text, (SELECT text_version FROM consent_current
                                      WHERE user_id = $1)) AS v) version
     WHERE v IS NOT NULL`,
    [
      userId,
      consent.textVersion ?? null,
      consent.analysis,
      consent.analysis && consent.researchCorpus,
    ],
  );
  if (rowCount === 0) throw new Error("name the text's version: --text-version");
}
