// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The collector (`pnpm start <command>`): follows players' Valve matches and queues their demos for the worker.
//
//   run [--once]   collect every COLLECTOR_INTERVAL_SECONDS (default 3600)
//   login          logs the bot in once, asking for Steam Guard, and keeps its refresh token
//   add-source     follows a player: --steam-id, --name, --share-code; the authentication
//                  code is asked on the terminal (or PLAYER_AUTH_CODE)
//                  --text-version V [--corpus] records their consent at the same time
//   consent        records a player's consent: --steam-id, --text-version, --corpus (box 2);
//                  --withdraw withdraws it (then remove-source stops following them)
//   sources        lists the followed players (never their authentication code)
//   update-source  --share-code to restart the chain there, --auth-code to type a new code
//   pause-source, resume-source
//   remove-source  --yes: stops following the player and deletes their authentication code
//                  (their matches and their access to the site stay)
//
// The source commands take --source <id>, or --steam-id when the player has a single source.
//
// Environment: UNTRADED_DATABASE_URL, UNTRADED_SECRET_KEY, STEAM_WEB_API_KEY, BOT_ACCOUNT_NAME,
// BOT_PASSWORD (login only), BOT_REFRESH_TOKEN (seeds the state), COLLECTOR_DATA_DIR.

import { join } from "node:path";
import { createInterface } from "node:readline/promises";
import { parseArgs } from "node:util";
import pg from "pg";
import { collect, type Deps, type GcSession } from "./collect.js";
import { connectionString, PgStore } from "./db.js";
import { type BotSession, openBotSession } from "./gc.js";
import { secretKey } from "./secrets.js";
import { nextShareCode } from "./share-codes.js";
import { formatSources, sourceRef } from "./sources.js";
import { loadState, saveState } from "./state.js";

const sleep = (ms: number) => new Promise<void>((done) => setTimeout(done, ms));

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`missing ${name}`);
  return value;
}

const statePath = () => join(process.env.COLLECTOR_DATA_DIR ?? "data", ".state.json");

async function bot(interactive: boolean): Promise<BotSession> {
  const path = statePath();
  const state = await loadState(path);
  return openBotSession(
    {
      refreshToken: state.botRefreshToken ?? process.env.BOT_REFRESH_TOKEN,
      accountName: requireEnv("BOT_ACCOUNT_NAME"),
      password: process.env.BOT_PASSWORD ?? "",
      interactive,
    },
    async (token) => {
      state.botRefreshToken = token;
      await saveState(path, state);
    },
  );
}

async function round(store: PgStore, maxMatches: number): Promise<void> {
  const apiKey = requireEnv("STEAM_WEB_API_KEY");
  let session: BotSession | undefined;
  const deps: Deps = {
    store,
    nextShareCode: (params) => nextShareCode({ apiKey, ...params }),
    gc: async (): Promise<GcSession> => {
      session ??= await bot(false);
      return session;
    },
    sleep,
    log: (message) => console.log(message),
  };
  try {
    for (const report of await collect(deps, maxMatches)) {
      const error = report.error ? `, ${report.error}` : "";
      console.log(`${report.source}: ${report.recorded} new match(es)${error}`);
    }
  } finally {
    session?.close();
  }
}

async function main(): Promise<void> {
  const { positionals, values } = parseArgs({
    allowPositionals: true,
    options: {
      once: { type: "boolean", default: false },
      "steam-id": { type: "string" },
      name: { type: "string" },
      "share-code": { type: "string" },
      source: { type: "string" },
      "auth-code": { type: "boolean", default: false },
      yes: { type: "boolean", default: false },
      "text-version": { type: "string" },
      corpus: { type: "boolean", default: false },
      withdraw: { type: "boolean", default: false },
    },
  });
  const command = positionals[0];

  if (command === "login") {
    const session = await bot(true);
    session.close();
    console.log(`logged in; refresh token kept in ${statePath()}`);
    return;
  }

  const pool = new pg.Pool({
    connectionString: connectionString(process.env.UNTRADED_DATABASE_URL),
  });
  const store = new PgStore(pool, secretKey(process.env.UNTRADED_SECRET_KEY));
  try {
    if (command === "add-source") {
      const steamId = values["steam-id"];
      const shareCode = values["share-code"];
      if (!steamId || !shareCode) throw new Error("add-source needs --steam-id and --share-code");
      const authCode = process.env.PLAYER_AUTH_CODE ?? (await ask("Authentication code: "));
      const id = await store.addSource({
        steamId,
        name: values.name ?? steamId,
        authCode,
        shareCode,
        consent: values["text-version"]
          ? { textVersion: values["text-version"], analysis: true, researchCorpus: values.corpus }
          : undefined,
      });
      console.log(`source ${id} added`);
    } else if (command === "consent") {
      const steamId = sourceRef({ "steam-id": values["steam-id"] }).steamId as string;
      if (!values.withdraw && !values["text-version"]) {
        throw new Error("consent needs --text-version (or --withdraw)");
      }
      await store.recordConsent(steamId, {
        textVersion: values["text-version"],
        analysis: !values.withdraw,
        researchCorpus: !values.withdraw && values.corpus,
      });
      console.log(values.withdraw ? "consent withdrawn" : "consent recorded");
    } else if (command === "sources") {
      for (const line of formatSources(await store.listSources())) console.log(line);
    } else if (command === "update-source") {
      const id = await store.findSource(sourceRef(values));
      const authCode = values["auth-code"]
        ? (process.env.PLAYER_AUTH_CODE ?? (await ask("New authentication code: ")))
        : undefined;
      await store.updateSource(id, { shareCode: values["share-code"], authCode });
      console.log(`source ${id} updated`);
    } else if (command === "pause-source" || command === "resume-source") {
      const id = await store.findSource(sourceRef(values));
      await store.updateSource(id, { enabled: command === "resume-source" });
      console.log(`source ${id} ${command === "resume-source" ? "resumed" : "paused"}`);
    } else if (command === "remove-source") {
      const id = await store.findSource(sourceRef(values));
      if (!values.yes)
        throw new Error(`remove-source deletes source ${id}: run it again with --yes`);
      await store.removeSource(id);
      console.log(`source ${id} removed`);
    } else if (command === "run") {
      const maxMatches = Number(process.env.MAX_MATCHES_PER_RUN ?? "20");
      const intervalMs = Number(process.env.COLLECTOR_INTERVAL_SECONDS ?? "3600") * 1000;
      while (true) {
        try {
          await round(store, maxMatches);
        } catch (error) {
          // Logged and retried at the next round: the service itself keeps running.
          console.error(error);
          if (values.once) throw error;
        }
        if (values.once) break;
        await sleep(intervalMs);
      }
    } else {
      throw new Error(
        "usage: untraded-collector run [--once] | login | add-source | consent | sources" +
          " | update-source" +
          " | pause-source | resume-source | remove-source",
      );
    }
  } finally {
    await pool.end();
  }
}

async function ask(question: string): Promise<string> {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  try {
    return (await rl.question(question)).trim();
  } finally {
    rl.close();
  }
}

main()
  .then(() => process.exit(0))
  .catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : error);
    process.exit(1);
  });
