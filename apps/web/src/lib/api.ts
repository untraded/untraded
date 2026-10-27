// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The API, called from the server only: the session cookie is forwarded as is, and row-level
// security in the database decides what comes back (apps/api).

import { cookies } from "next/headers";
import { notFound } from "next/navigation";

export const SESSION_COOKIE = "untraded_session";

/** How the web server reaches the API (in a container: the service name). */
export function internalApiUrl(): string {
  return (process.env.UNTRADED_API_INTERNAL_URL ?? "http://localhost:8000").replace(/\/$/, "");
}

export { PUBLIC_API_PATH } from "./api-path";

export interface Consent {
  text_version: string;
  /** Box 1, required: false means the player withdrew their consent. */
  analysis: boolean;
  /** Box 2, optional: their raw demos join the research corpus. */
  research_corpus: boolean;
  recorded_at: string;
}

/** How the collector follows the player's Valve matches. */
export interface MySource {
  enabled: boolean;
  last_success_at: string | null;
  /** `403`: their authentication code changed; `412`: the known share code is too old. */
  last_error: string | null;
}

export interface Me {
  id: string;
  steam_id: string;
  display_name: string;
  admin: boolean;
  /** The player's current consent; null before they give it. */
  consent: Consent | null;
  /** The current consent text: a consent naming another version must be given again. */
  consent_version: string;
  /** Null before they give their codes. */
  source: MySource | null;
  /** Whether this server can keep the codes. */
  can_add_source: boolean;
}

export type PlayerState = "invited" | "joined" | "consented" | "followed" | "paused" | "withdrawn";

export interface AdminPlayer {
  steam_id: string;
  display_name: string;
  state: PlayerState;
  invited_at: string | null;
  joined_at: string | null;
  last_seen_at: string | null;
  consent: Consent | null;
  source: (MySource & { id: string }) | null;
  /** Their analysed matches. */
  matches: number;
  last_match_at: string | null;
}

/** A Steam account that signed in without an invitation and asked for one. */
export interface InvitationRequest {
  steam_id: string;
  /** The public Steam name, when the API could read it. */
  persona_name: string | null;
  requested_at: string;
}

export interface Health {
  database_bytes: number;
  /** Jobs by status (`queued`, `running`, `failed`...). */
  jobs: Record<string, number>;
  failed_jobs: { kind: string; attempts: number; error: string | null; at: string }[];
  /** Matches collected in the last 7 days, by status. */
  matches_7_days: Record<string, number>;
  sources: { total: number; paused: number; erroring: number };
  backups: {
    last: { name: string; at: string; bytes: number } | null;
    daily: number;
    weekly: number;
    /** What the off-site copy wrote, as is; null when there is none. */
    offsite: Record<string, unknown> | null;
  };
  disk: { total: number; free: number } | null;
}

export interface PlayerLine {
  kills: number | null;
  deaths: number | null;
  adr: number | null;
  kast: number | null;
  hltv1: number | null;
  untraded_deaths: number | null;
}

export type MatchStatus =
  | "pending"
  | "downloading"
  | "parsing"
  | "ready"
  | "failed"
  | "unavailable";
export type Result = "win" | "loss" | "tie";

export interface MatchSummary {
  id: string;
  played_at: string | null;
  ended_at: string | null;
  mode: string;
  status: MatchStatus;
  map: string | null;
  score_a: number | null;
  score_b: number | null;
  rounds_played: number | null;
  my_team: "A" | "B" | null;
  my_result: Result | null;
  my_line: PlayerLine | null;
}

export interface MatchList {
  items: MatchSummary[];
  limit: number;
  offset: number;
}

export interface Round {
  round: number;
  winner_side: "CT" | "T" | null;
  winner_team: "A" | "B" | null;
  reason: string;
  ct_team: "A" | "B";
  score_a: number;
  score_b: number;
  is_overtime: boolean;
  bomb_site: string | null;
  bomb_planted: boolean;
}

export interface Player {
  steam_id: string;
  name: string;
  team: "A" | "B";
  rank: number | null;
  rounds_on_team: number;
  line: PlayerLine;
}

export interface MatchDetail extends MatchSummary {
  team_a_name: string | null;
  team_b_name: string | null;
  tickrate: number | null;
  unavailable: string[];
  error: string | null;
  rounds: Round[];
  players: Player[];
}

/** One metric of one player in one match, on the whole match (`match`) or on one side. */
export interface MetricValue {
  metric_id: string;
  version: string;
  name: string;
  unit: string;
  better: Comparison["better"];
  scope: "match" | "ct" | "t";
  value: number | null;
}

export interface PlayerMetrics {
  match_id: string;
  steam_id: string;
  metrics: MetricValue[];
}

/** Why a demo sent now would be refused, before sending it (`GET /uploads`). */
export type UploadRefusal = "off" | "disk_full" | "consent" | "quota" | "busy";

/** A demo the player sent, and what became of it. */
export interface UploadLine {
  upload_id: string;
  /** The match it became, or the one it already was (a demo sent twice): open it once ready. */
  match_id: string;
  received_at: string;
  mode: string;
  map: string | null;
  played_at: string | null;
  state: "processing" | "ready" | "refused" | "failed";
  /** Why it was refused or failed: `not_a_demo`, `corrupt`, `too_large`, `unsupported_mode`,
   * `not_a_player`, `parse_failed`. */
  reason: string | null;
}

export interface UploadList {
  items: UploadLine[];
  refusal: UploadRefusal | null;
  /** The largest file the API takes. */
  max_bytes: number;
}

/** The cookie header to forward: only our session cookie. */
async function sessionHeader(): Promise<Record<string, string>> {
  const session = (await cookies()).get(SESSION_COOKIE);
  return session ? { cookie: `${SESSION_COOKIE}=${session.value}` } : {};
}

export class ApiError extends Error {}

/** GET from the API. `null` when not signed in; `notFound()` on 404. */
export async function apiGet<T>(path: string): Promise<T | null> {
  const response = await fetch(`${internalApiUrl()}${path}`, {
    headers: await sessionHeader(),
    cache: "no-store",
  });
  if (response.status === 401) return null;
  if (response.status === 404) notFound();
  if (!response.ok) throw new ApiError(`API ${path}: HTTP ${response.status}`);
  return (await response.json()) as T;
}

/**
 * GET from the API, tolerant: `null` on any failure (not signed in, missing, server error, no
 * answer), for data a page can do without, such as the matches behind a priority's evidence.
 */
export async function apiGetOptional<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${internalApiUrl()}${path}`, {
      headers: await sessionHeader(),
      cache: "no-store",
    });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

/** What a write answered: its status, and the `detail` of an error (e.g. `{ field }` on 422). */
export interface ApiResult {
  ok: boolean;
  status: number;
  detail: unknown;
}

/** Sends a write to the API with the session cookie, and says how it went. A server that does
 * not answer reads as a 503. */
export async function apiSend(
  path: string,
  method: "POST" | "PUT" | "DELETE",
  body?: unknown,
): Promise<ApiResult> {
  const headers: Record<string, string> = await sessionHeader();
  if (body !== undefined) headers["content-type"] = "application/json";
  try {
    const response = await fetch(`${internalApiUrl()}${path}`, {
      method,
      headers,
      body: body === undefined ? null : JSON.stringify(body),
      cache: "no-store",
    });
    const text = response.ok ? "" : await response.text();
    let detail: unknown = null;
    try {
      detail = text ? (JSON.parse(text) as { detail?: unknown }).detail : null;
    } catch {
      detail = null;
    }
    return { ok: response.ok, status: response.status, detail };
  } catch {
    return { ok: false, status: 503, detail: null };
  }
}

/** The field a 422 names (`{ detail: { field } }`), if any. */
export function refusedField(result: ApiResult): string | null {
  const detail = result.detail as { field?: unknown } | null;
  return result.status === 422 && typeof detail?.field === "string" ? detail.field : null;
}

/** POST to the API with the session cookie, and a JSON body if given. */
export async function apiPost(path: string, body?: unknown): Promise<void> {
  const headers: Record<string, string> = await sessionHeader();
  if (body !== undefined) headers["content-type"] = "application/json";
  await fetch(`${internalApiUrl()}${path}`, {
    method: "POST",
    headers,
    body: body === undefined ? null : JSON.stringify(body),
    cache: "no-store",
  });
}

export interface Comparison {
  metric_id: string;
  version: string;
  name: string;
  unit: string;
  /** Which way is an improvement. */
  better: "higher" | "lower" | "neutral";
  /** `value`, or `per_round` for totals compared per round played. */
  basis: "value" | "per_round";
  session: number | null;
  reference: number | null;
  delta: number | null;
  /** What a rate or an average stands on in this session: the rounds played, or its cases (the
   * opening duels for the opening success). `null` for totals, or when a count it rests on is
   * missing. */
  cases: number | null;
  /** The value can be negative (K-D): a gap in % of the reference means nothing for it. */
  signed: boolean;
}

export interface SessionSummary {
  id: string;
  started_at: string;
  ended_at: string;
  matches: number;
  rounds: number;
  wins: number;
  losses: number;
  ties: number;
  enough: boolean;
  headlines: Comparison[];
  /** Its matches, in the order played. */
  maps: PlayedMap[];
  /** Its first priority; `null` when no rule fired. */
  top_priority: TopPriority | null;
}

/** A match of a session, as the list of sessions shows it. */
export interface PlayedMap {
  match_id: string;
  map: string | null;
  /** For the player; `null` when the score is unknown. */
  result: Result | null;
  my_score: number | null;
  their_score: number | null;
}

/** A session's first priority, as the list of sessions shows it (the report has them all). */
export interface TopPriority {
  rule_id: string;
  message_key: string;
  args: Record<string, unknown>;
  cost: number;
  rounds_touched: number;
  rounds_lost: number;
}

export interface SessionList {
  items: SessionSummary[];
  limit: number;
  offset: number;
}

export interface AdviceEvent {
  match_id: string;
  round: number;
  tick: number;
  /** A few seconds before the event: `demo_gototick` lands just before it. */
  goto_tick: number;
  map?: string;
  side?: string;
  zone?: string;
  [detail: string]: unknown;
}

export interface Advice {
  id: string;
  rule_id: string;
  rule_version: string;
  priority: number;
  message_key: string;
  args: {
    metric: string;
    unit: string;
    basis: Comparison["basis"] | "pattern";
    session: number | null;
    reference: number | null;
    events: number;
    rounds_touched: number;
    rounds_lost: number;
    actions: string[];
    indicator: string;
    map?: string;
    side?: string;
    zone?: string;
    history_events?: number;
  };
  evidence: AdviceEvent[];
  cost: number;
  my_vote: 1 | -1 | null;
}

export interface FollowUp {
  rule_id: string;
  indicator: string;
  name: string;
  unit: string;
  basis: Comparison["basis"];
  better: Comparison["better"];
  /** The indicator in the session that raised the priority. */
  then: number | null;
  now: number | null;
  reference: number | null;
  /** Oldest first, this session last. */
  history: { session_id: string; started_at: string; value: number | null }[];
}

export interface SessionReport extends SessionSummary {
  advice: Advice[];
  follow_up: FollowUp[];
  reference: {
    /** `self`, `level` (players of the same rating band) or `none`. */
    kind: "self" | "level" | "none";
    level_low: number | null;
    level_high: number | null;
    since: string;
    until: string;
    matches: number;
    rounds: number;
    enough: boolean;
    min_matches: number;
    min_rounds: number;
  };
  match_list: MatchSummary[];
  metrics: Comparison[];
}

export const getMe = () => apiGet<Me>("/me");
export const getMatches = (offset = 0) => apiGet<MatchList>(`/matches?limit=30&offset=${offset}`);
export const getSessions = (offset = 0) =>
  apiGet<SessionList>(`/sessions?limit=20&offset=${offset}`);
export const getSession = (id: string) =>
  apiGet<SessionReport>(`/sessions/${encodeURIComponent(id)}`);
export const getMatch = (id: string) => apiGet<MatchDetail>(`/matches/${encodeURIComponent(id)}`);
export const getAdminPlayers = () => apiGet<{ items: AdminPlayer[] }>("/admin/players");
export const getAdminHealth = () => apiGet<Health>("/admin/health");
export const getInvitationRequests = () =>
  apiGet<{ items: InvitationRequest[] }>("/admin/invitation-requests");
/** A match the page can do without: `null` when it is missing or the API fails. */
export const findMatch = (id: string) =>
  apiGetOptional<MatchDetail>(`/matches/${encodeURIComponent(id)}`);
/** A player's metrics in a match, on each scope: `null` when the API cannot give them. */
export const findPlayerMetrics = (matchId: string, steamId: string) =>
  apiGetOptional<PlayerMetrics>(
    `/matches/${encodeURIComponent(matchId)}/players/${encodeURIComponent(steamId)}`,
  );

/** How many pages of sessions to look through for a match's session (20 per page). */
const SESSION_PAGES = 5;

/**
 * The session a match belongs to, found in the list of sessions (newest first): `null` when none
 * holds it, or when the API fails. Stops at the first page that reaches back before the match.
 */
export async function findSessionOf(
  matchId: string,
  playedAt: string | null,
): Promise<SessionSummary | null> {
  const played = playedAt ? Date.parse(playedAt) : Number.NaN;
  for (let page = 0; page < SESSION_PAGES; page++) {
    const list = await apiGetOptional<SessionList>(`/sessions?limit=20&offset=${page * 20}`);
    if (!list) return null;
    const found = list.items.find((s) => s.maps.some((m) => m.match_id === matchId));
    if (found) return found;
    const oldest = list.items.at(-1);
    if (list.items.length < list.limit || !oldest || Date.parse(oldest.started_at) < played) {
      return null;
    }
  }
  return null;
}

/** A session's report the page can do without: `null` when it is missing or the API fails. */
export const findSession = (id: string) =>
  apiGetOptional<SessionReport>(`/sessions/${encodeURIComponent(id)}`);
export const getUploads = () => apiGet<UploadList>("/uploads");

/** How many pages of sessions the progress page reads at most (20 per page). */
const PROGRESS_PAGES = 10;

/**
 * The player's sessions, newest first, back to `since` (an instant; `null` for all of them) or
 * until `count` are read. `null` when not signed in.
 */
export async function sessionsBack(
  since: number | null,
  count: number | null,
): Promise<SessionSummary[] | null> {
  const found: SessionSummary[] = [];
  for (let page = 0; page < PROGRESS_PAGES; page++) {
    const list = await apiGet<SessionList>(`/sessions?limit=20&offset=${page * 20}`);
    if (!list) return page === 0 ? null : found;
    found.push(...list.items);
    const oldest = list.items.at(-1);
    if (
      list.items.length < list.limit ||
      !oldest ||
      (since !== null && Date.parse(oldest.started_at) < since) ||
      (count !== null && found.length >= count)
    ) {
      break;
    }
  }
  return found;
}
