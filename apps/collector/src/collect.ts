// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// One collection round: for each followed player, walk the share-code chain from the last
// known code, ask the Game Coordinator for each new match's demo URL, and record the match with
// its `download` job (the worker takes it from there).

import { decodeMatchShareCode } from "csgo-sharecode";
import type { MatchInfo } from "globaloffensive";
import type { FoundMatch, Source, Store } from "./db.js";
import type { NextCodeResult } from "./share-codes.js";

export const WEB_API_DELAY_MS = 1_500;
export const GC_DELAY_MS = 2_000;

export interface GcSession {
  requestMatch(shareCode: string): Promise<MatchInfo>;
}

export interface Deps {
  store: Store;
  nextShareCode(params: {
    steamId: string;
    authCode: string;
    knownCode: string;
  }): Promise<NextCodeResult>;
  /** Opened on the first new match of the round, then reused. */
  gc(): Promise<GcSession>;
  sleep(ms: number): Promise<void>;
  log(message: string): void;
}

export interface SourceReport {
  source: string;
  recorded: number;
  error?: string;
}

/** What the Game Coordinator tells about a match. */
export function foundMatch(shareCode: string, info: MatchInfo): FoundMatch {
  const lastRound = info.roundstatsall?.at(-1);
  return {
    shareCode,
    matchId: decodeMatchShareCode(shareCode).matchId.toString(),
    url: lastRound?.map || undefined,
    playedAt: info.matchtime ? new Date(info.matchtime * 1000) : undefined,
  };
}

/** New share codes after the source's known one, oldest first; at most `max`. */
async function newCodes(
  source: Source,
  deps: Deps,
  max: number,
): Promise<{ codes: string[]; error?: string }> {
  const codes: string[] = [];
  let known = source.knownShareCode;
  if (!known) return { codes, error: "no known share code: add one to the source" };
  while (codes.length < max) {
    const result = await deps.nextShareCode({
      steamId: source.steamId,
      authCode: source.authCode,
      knownCode: known,
    });
    if (result.kind === "none") break;
    if (result.kind === "fatal") return { codes, error: `${result.status}: ${result.reason}` };
    if (result.kind === "retry") {
      deps.log(`${source.id}: Steam Web API answered ${result.status}, next round`);
      break;
    }
    codes.push(result.code);
    known = result.code;
    await deps.sleep(WEB_API_DELAY_MS);
  }
  return { codes };
}

export async function collectSource(
  source: Source,
  deps: Deps,
  maxMatches: number,
): Promise<SourceReport> {
  const report: SourceReport = { source: source.id, recorded: 0 };
  const { codes, error } = await newCodes(source, deps, maxMatches);
  for (const shareCode of codes) {
    const matchId = decodeMatchShareCode(shareCode).matchId.toString();
    if (await deps.store.hasMatch(matchId)) {
      await deps.store.advance(source, shareCode); // brought by another followed player
      continue;
    }
    try {
      const session = await deps.gc();
      const match = foundMatch(shareCode, await session.requestMatch(shareCode));
      await deps.store.recordMatch(source, match);
      report.recorded++;
      deps.log(`${source.id}: match ${matchId} ${match.url ? "queued" : "has no demo"}`);
    } catch (failure) {
      // The known code stays before this match, so the next round retries it.
      report.error = `match ${matchId}: ${String(failure)}`;
      break;
    }
    await deps.sleep(GC_DELAY_MS);
  }
  if (error && !report.error) report.error = error;
  await deps.store.sourceDone(source, report.error);
  return report;
}

export async function collect(deps: Deps, maxMatches: number): Promise<SourceReport[]> {
  const reports: SourceReport[] = [];
  for (const source of await deps.store.sources()) {
    reports.push(await collectSource(source, deps, maxMatches));
  }
  return reports;
}
