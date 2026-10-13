// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// Spike S0.1: from the last known share code to downloaded demos, without human intervention.
// Run once per hour (cron). Appends one JSON line per match to out/matches.jsonl.

import { appendFile, mkdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { decodeMatchShareCode } from "csgo-sharecode";
import { downloadDemo } from "./download.js";
import { type BotSession, openBotSession } from "./gc.js";
import { nextShareCode } from "./share-codes.js";
import { loadState, saveState } from "./state.js";

const SPIKE_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");
// State and logs live next to the spike by default, or in a mounted volume (Docker: /data).
const DATA_DIR = process.env.SPIKE_DATA_DIR ?? SPIKE_DIR;
const STATE_PATH = join(DATA_DIR, ".state.json");
const LOG_PATH = join(DATA_DIR, "out", "matches.jsonl");
const WEB_API_DELAY_MS = 1_500;
const GC_DELAY_MS = 2_000;

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`missing ${name} in .env (see .env.example)`);
  return value;
}

const sleep = (ms: number) => new Promise((done) => setTimeout(done, ms));

async function log(entry: Record<string, unknown>): Promise<void> {
  await mkdir(dirname(LOG_PATH), { recursive: true });
  await appendFile(LOG_PATH, `${JSON.stringify({ at: new Date().toISOString(), ...entry })}\n`);
}

async function main(): Promise<void> {
  try {
    process.loadEnvFile(join(SPIKE_DIR, ".env"));
  } catch {
    // No .env is fine when the variables come from the environment (Docker, Portainer).
    if (!process.env.STEAM_WEB_API_KEY) {
      throw new Error(
        "no .env file: copy .env.example to .env in spikes/S0.1-valve and fill it in",
      );
    }
  }
  const apiKey = requireEnv("STEAM_WEB_API_KEY");
  const steamId = requireEnv("PLAYER_STEAMID64");
  const authCode = requireEnv("PLAYER_AUTH_CODE");
  const corpusDir = requireEnv("UNTRADED_CORPUS_DIR");
  const maxMatches = Number(process.env.MAX_MATCHES_PER_RUN ?? "20");

  const state = await loadState(STATE_PATH);
  let knownCode = state.knownShareCode ?? requireEnv("PLAYER_INITIAL_SHARE_CODE");

  // 1. Walk the share-code chain (Steam Web API, no bot needed).
  const newCodes: string[] = [];
  while (newCodes.length < maxMatches) {
    const result = await nextShareCode({ apiKey, steamId, authCode, knownCode });
    if (result.kind === "next") {
      newCodes.push(result.code);
      knownCode = result.code;
      await sleep(WEB_API_DELAY_MS);
      continue;
    }
    if (result.kind === "fatal") {
      await log({ event: "chain_broken", status: result.status, reason: result.reason });
      throw new Error(`share-code chain stopped (${result.status}): ${result.reason}`);
    }
    if (result.kind === "retry") await log({ event: "web_api_retry", status: result.status });
    break;
  }
  const pending = newCodes.filter((code) => !state.processedShareCodes.includes(code));
  console.log(`${pending.length} new match(es) since the last run`);
  if (pending.length === 0) return;

  // 2. Resolve demo URLs through the Game Coordinator, then download.
  let session: BotSession | undefined;
  try {
    const gcStarted = performance.now();
    session = await openBotSession(
      {
        // BOT_REFRESH_TOKEN seeds a fresh volume, so no Steam Guard code is needed in a container.
        refreshToken: state.botRefreshToken ?? process.env.BOT_REFRESH_TOKEN,
        accountName: requireEnv("BOT_ACCOUNT_NAME"),
        password: process.env.BOT_PASSWORD ?? "",
      },
      async (token) => {
        state.botRefreshToken = token;
        await saveState(STATE_PATH, state);
      },
    );
    await log({ event: "gc_connected", seconds: (performance.now() - gcStarted) / 1000 });

    for (const shareCode of pending) {
      const matchId = decodeMatchShareCode(shareCode).matchId.toString();
      const requested = performance.now();
      try {
        const match = await session.requestMatch(shareCode);
        const gcSeconds = (performance.now() - requested) / 1000;
        const lastRound = match.roundstatsall?.at(-1);
        const url = lastRound?.map;
        const matchTime = match.matchtime ? new Date(match.matchtime * 1000) : undefined;
        const durationS = lastRound?.match_duration;
        const endedAt =
          matchTime && durationS ? new Date(matchTime.getTime() + durationS * 1000) : undefined;

        if (!url) {
          console.log(`${matchId}: no demo URL`);
          await log({ event: "no_demo_url", shareCode, matchId, gcSeconds });
        } else {
          console.log(`${matchId}: downloading ${url}`);
          const destination = join(corpusDir, "inbox", `${matchId}.dem.bz2`);
          const download = await downloadDemo(url, destination);
          console.log(`${matchId}: ${JSON.stringify(download)}`);
          await log({
            event: "match",
            shareCode,
            matchId,
            url,
            matchTime: matchTime?.toISOString(),
            endedAt: endedAt?.toISOString(),
            minutesSinceEnd: endedAt ? (Date.now() - endedAt.getTime()) / 60_000 : undefined,
            scores: lastRound?.team_scores,
            gcSeconds,
            download,
          });
          // Keep the known code where it is, so the next run retries (and resumes) this demo.
          if (download.kind === "error") break;
        }
        state.processedShareCodes.push(shareCode);
        state.knownShareCode = shareCode;
        await saveState(STATE_PATH, state);
      } catch (error) {
        // Stop here: the known code is not advanced, so the next run retries this match.
        console.error(`${matchId}: ${String(error)}`);
        await log({ event: "match_error", shareCode, matchId, error: String(error) });
        break;
      }
      await sleep(GC_DELAY_MS);
    }
  } finally {
    session?.close();
  }
}

main()
  .then(() => process.exit(0))
  .catch(async (error: unknown) => {
    console.error(error);
    await log({ event: "run_failed", error: String(error) }).catch(() => undefined);
    process.exit(1);
  });
