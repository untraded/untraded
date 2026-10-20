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

/** How browsers reach the API (sign-in links). */
export function publicApiUrl(): string {
  return (process.env.UNTRADED_API_PUBLIC_URL ?? "http://localhost:8000").replace(/\/$/, "");
}

export interface Me {
  id: string;
  steam_id: string;
  display_name: string;
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

/** POST to the API with the session cookie (sign-out). */
export async function apiPost(path: string): Promise<void> {
  await fetch(`${internalApiUrl()}${path}`, {
    method: "POST",
    headers: await sessionHeader(),
    cache: "no-store",
  });
}

export interface Comparison {
  metric_id: string;
  version: string;
  name: string;
  unit: string;
  /** `value`, or `per_round` for totals compared per round played. */
  basis: "value" | "per_round";
  session: number | null;
  reference: number | null;
  delta: number | null;
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
}

export interface SessionList {
  items: SessionSummary[];
  limit: number;
  offset: number;
}

export interface SessionReport extends SessionSummary {
  reference: {
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
