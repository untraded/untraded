<!--
SPDX-FileCopyrightText: 2026 The Untraded Authors
SPDX-License-Identifier: AGPL-3.0-only
-->

# Self-hosting

`compose.yaml` runs the ingestion chain: the Valve matches of the players you follow are
downloaded, parsed and analysed into PostgreSQL. There is no web interface yet (phase 2 is
under way, see `docs/roadmap.md`): you query the database, or the Parquet tables in the store.

```
collector ──(match + download job)──▶ PostgreSQL ◀──(parse job, tables, metrics)── worker
   │ Steam Web API, Game Coordinator                                    │ demo and Parquet store
```

| Service | Image | Role |
|---|---|---|
| `db` | `postgres:16` | everything, including the job queue (ADR 0004, 0011) |
| `migrate` | `apps/worker/Dockerfile` | applies the migrations, then exits (`untraded-db upgrade`) |
| `worker` | `apps/worker/Dockerfile` | `download` and `parse` jobs, raw demo retention (`apps/worker`) |
| `collector` | `apps/collector/Dockerfile` | follows players' Valve matches (`apps/collector`) |

Every image builds on amd64 and arm64.

## What you need

- Docker with Compose.
- A **secondary Steam account** for the bot, never your main one. A free account works: the
  collector asks for the free CS2 license itself.
- A Steam Web API key, from your main account (<https://steamcommunity.com/dev/apikey>).
- For each player to follow, their **match history authentication code** and a **recent share
  code** (both in CS2's match history settings, or at
  <https://help.steampowered.com/en/wizard/HelpWithGameIssue/?appid=730&issueid=128>).

## Configuration

Put these in a `.env` next to `compose.yaml` (it is ignored by git), or in your orchestrator's
stack variables.

| Variable | Required | Role |
|---|---|---|
| `UNTRADED_DB_PASSWORD` | yes | PostgreSQL password (letters and digits: it goes into a URL) |
| `UNTRADED_SECRET_KEY` | yes | 32 random bytes, base64 (`openssl rand -base64 32`): encrypts the authentication codes in the database. Losing it means adding the sources again |
| `STEAM_WEB_API_KEY` | yes | Steam Web API key |
| `BOT_ACCOUNT_NAME` | yes | the bot's account name |
| `BOT_REFRESH_TOKEN` | first start | the bot's refresh token, if you have one (see below) |
| `UNTRADED_DEMO_RETENTION_DAYS` | no | days to keep raw demos after parsing; unset keeps them, `0` deletes them once parsed |
| `COLLECTOR_INTERVAL_SECONDS` | no | time between collection rounds (3600) |

## First start

```bash
docker compose up -d --build
```

Then, once:

1. **Log the bot in.** Steam Guard asks for a code, so this needs a terminal:

   ```bash
   docker compose run --rm -it -e BOT_PASSWORD collector ./node_modules/.bin/tsx src/main.ts login
   ```

   with `BOT_PASSWORD` set in your shell. The refresh token is kept in the `collector-data`
   volume, and later starts need neither the password nor a code. If you already have a
   refresh token, set `BOT_REFRESH_TOKEN` instead.

2. **Follow a player:**

   ```bash
   docker compose exec -it collector ./node_modules/.bin/tsx src/main.ts add-source \
     --steam-id 7656119XXXXXXXXXX --name me --share-code CSGO-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
   ```

   It asks for the authentication code. The share code is where the chain starts: the
   matches after it are collected.

The next round (or `docker compose restart collector`) picks the player up.

## Checking it works

```bash
docker compose logs -f collector worker
docker compose exec db psql -U untraded -c \
  "SELECT status, count(*) FROM match GROUP BY status"
docker compose exec db psql -U untraded -c \
  "SELECT kind, status, attempts, last_error FROM job ORDER BY id DESC LIMIT 10"
```

A match goes `downloading`, then `parsing`, then `ready`. Other outcomes:

- `unavailable`: Valve no longer has the demo, or the match is not a Premier match. The
  share-code chain also holds Competitive and Wingman matches, and the worker sets them aside.
- `failed`: the job used up its attempts, and `match.error` tells why.

## Data

| Volume | Holds | Back it up |
|---|---|---|
| `db-data` | PostgreSQL | yes (`pg_dump`) |
| `store` | raw demos (`demos/`) and Parquet per match (`matches/`) | the Parquet, at least: metrics are recomputed from it (ADR 0009) |
| `collector-data` | the bot's refresh token (`.state.json`, mode 600) | no: log in again instead |

## Updating

```bash
git pull && docker compose up -d --build
```

`migrate` applies any new migration before the services start.
