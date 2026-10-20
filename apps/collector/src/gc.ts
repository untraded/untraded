// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

import { createInterface } from "node:readline/promises";
import GlobalOffensive, { type MatchInfo } from "globaloffensive";
import SteamUser from "steam-user";

const CS2_APP_ID = 730;
const GC_CONNECT_TIMEOUT_MS = 60_000;
const MATCH_REQUEST_TIMEOUT_MS = 30_000;

export interface BotCredentials {
  refreshToken?: string | undefined;
  accountName: string;
  password: string;
  /** Asks for a Steam Guard code on the terminal (`login`); a service fails instead. */
  interactive: boolean;
}

export interface BotSession {
  /** Asks the Game Coordinator for the full info of one match. */
  requestMatch(shareCode: string): Promise<MatchInfo>;
  close(): void;
}

/** Rejects after `ms`, except while `paused()` is true (the deadline is pushed back meanwhile). */
function withTimeout<T>(
  promise: Promise<T>,
  ms: number,
  what: string,
  paused: () => boolean = () => false,
): Promise<T> {
  return Promise.race([
    promise,
    new Promise<never>((_, reject) => {
      const check = () => {
        if (paused()) setTimeout(check, ms).unref();
        else reject(new Error(`timeout after ${ms} ms: ${what}`));
      };
      setTimeout(check, ms).unref();
    }),
  ]);
}

async function askSteamGuardCode(domain: string | null, lastCodeWrong: boolean): Promise<string> {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const where = domain ? `e-mail (${domain})` : "mobile authenticator";
  const prefix = lastCodeWrong ? "Wrong code. " : "";
  const code = await rl.question(`${prefix}Steam Guard code from ${where}: `);
  rl.close();
  return code.trim();
}

/**
 * Logs the bot in, launches CS2 and waits for a Game Coordinator session.
 * `onRefreshToken` receives the token to persist, so later runs need no password or Steam Guard
 * code.
 */
export async function openBotSession(
  credentials: BotCredentials,
  onRefreshToken: (token: string) => Promise<void>,
): Promise<BotSession> {
  const user = new SteamUser({ autoRelogin: false });
  const csgo = new GlobalOffensive(user);

  // Time spent typing the Steam Guard code must not count against the logon timeout.
  let waitingForCode = false;
  let refused: ((error: Error) => void) | undefined;
  user.on("steamGuard", (domain, callback, lastCodeWrong) => {
    if (!credentials.interactive) {
      refused?.(new Error("Steam Guard code needed: run `untraded-collector login` once"));
      return;
    }
    waitingForCode = true;
    void askSteamGuardCode(domain, lastCodeWrong).then((code) => {
      waitingForCode = false;
      callback(code);
    });
  });
  user.on("refreshToken", (token) => {
    void onRefreshToken(token);
  });

  const loggedOn = new Promise<void>((resolve, reject) => {
    refused = reject;
    user.once("loggedOn", () => resolve());
    user.once("error", reject);
  });
  user.logOn(
    credentials.refreshToken
      ? { refreshToken: credentials.refreshToken }
      : { accountName: credentials.accountName, password: credentials.password },
  );
  try {
    await withTimeout(loggedOn, GC_CONNECT_TIMEOUT_MS, "Steam logon", () => waitingForCode);

    // Idempotent: grants the free CS2 license if the bot does not own it yet.
    await user.requestFreeLicense([CS2_APP_ID]);

    const connected = new Promise<void>((resolve) => csgo.once("connectedToGC", resolve));
    user.gamesPlayed([CS2_APP_ID]);
    await withTimeout(connected, GC_CONNECT_TIMEOUT_MS, "Game Coordinator session");
  } catch (error) {
    user.logOff();
    throw error;
  }

  return {
    async requestMatch(shareCode: string): Promise<MatchInfo> {
      const response = new Promise<MatchInfo>((resolve, reject) => {
        csgo.once("matchList", (matches) => {
          const match = matches[0];
          if (match) resolve(match);
          else reject(new Error("empty matchList (see node-globaloffensive issue #121)"));
        });
      });
      csgo.requestGame(shareCode);
      return withTimeout(response, MATCH_REQUEST_TIMEOUT_MS, `match info for ${shareCode}`);
    },
    close(): void {
      user.gamesPlayed([]);
      user.logOff();
    },
  };
}
