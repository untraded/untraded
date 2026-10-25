<!--
SPDX-FileCopyrightText: 2026 The Untraded Authors
SPDX-License-Identifier: AGPL-3.0-only
-->

# Self-hosting

`compose.yaml` runs Untraded: the Valve matches of the players you follow are downloaded,
parsed and analysed into PostgreSQL, and the site shows each player their sessions and matches
after signing in with Steam. Phase 2 is under way (see `docs/roadmap.md`).

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
| `api` | `apps/api/Dockerfile` | Steam sign-in, matches and session reports, under row-level security (`apps/api`) |
| `web` | `apps/web/Dockerfile` | the site; it relays `/api/*` to `api`, so it is the only published service (`apps/web`) |

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
| `UNTRADED_ADMIN_STEAM_IDS` | for invitations | SteamID64s of the admins, comma-separated. They invite players and follow the collector and the backups from the site's admin pages (API: `/admin`) |
| `UNTRADED_CONSENT_VERSION` | no | the version of the consent text invited players agree to on the site (`1`). Change it when the text changes: players then agree again |
| `UNTRADED_ALLOW_PRIVATE_DEMO_URLS` | no | `1` lets the worker download demos from private addresses (a server on your own network). Off by default: a demo URL never reaches a private, loopback or cloud metadata address |
| `UNTRADED_BACKUP_HOUR`, `UNTRADED_BACKUP_KEEP_DAYS`, `UNTRADED_BACKUP_KEEP_WEEKS` | no | when the daily database dump runs (3, UTC) and how many are kept: 7 daily, plus 4 weekly (Sunday's) |
| `COLLECTOR_INTERVAL_SECONDS` | no | time between collection rounds (3600) |
| `UNTRADED_SITE_URL` | for the site | the site's address as browsers see it, e.g. `https://untraded.example.com` (default `http://localhost:3000`). Steam sends users back there after signing in, and `https` makes the session cookie `Secure` |
| `UNTRADED_BIND`, `UNTRADED_WEB_PORT`, `UNTRADED_API_PORT` | no | where the web and the API are published for the reverse proxy (`127.0.0.1`, ports 3000 and 8000); `172.17.0.1` lets a reverse proxy running in Docker reach them |
| `UNTRADED_UPLOAD_MAX_MB`, `UNTRADED_UPLOAD_MAX_DEMO_GB` | no | the largest demo a player may send from the site (400 MB), and once decompressed (1.5 GB) |
| `UNTRADED_UPLOADS_PER_DAY`, `UNTRADED_UPLOADS_IN_FLIGHT` | no | uploads per player in 24 hours (20) and still being analysed (3); `0` lifts a limit |
| `UNTRADED_UPLOAD_MIN_FREE_GB` | no | uploads are refused while the disk has less free space (5) |
| `UNTRADED_OPERATOR_NAME`, `UNTRADED_OPERATOR_EMAIL` | for invited players | who runs this instance and where players write to use their rights: the consent text names them as the data controller |
| `UNTRADED_HOSTING` | no | where the data lives, as the consent text states it, e.g. `Oracle Cloud, Frankfurt (EU); backups on Hetzner, Germany`. Unset, the text asks players to write to the operator |
| `UNTRADED_TIME_ZONE` | no | time zone of the dates on the site until each player's browser sends its own (`Europe/Paris`), as an IANA name such as `America/New_York`; an unknown name falls back to `Europe/Paris` |

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

The next round (or `docker compose restart collector`) picks the player up. `add-source` also
**invites** the player to the site: signing in is open only to Steam accounts with a user.

If you follow other players, record their consent with `--text-version` (and `--corpus` for the
research corpus) on `add-source`, or later with the `consent` command.

**From the site** (admins only): invite a player by their SteamID64. Their first sign-in with
Steam creates their account; they then agree to the consent text and give their two codes, which
the API checks with Steam and stores encrypted. No command line, and the admin never sees the
codes.

The collector also lists, fixes, pauses and removes the followed players (`sources`,
`update-source`, `pause-source`, `resume-source`, `remove-source`): see
[`apps/collector/README.md`](../apps/collector/README.md#commands). For example, after a
player changes their authentication code:

```bash
docker compose exec -it collector ./node_modules/.bin/tsx src/main.ts update-source   --steam-id 7656119XXXXXXXXXX --auth-code
```

## The site

Put a reverse proxy with HTTPS in front of the web, for example Caddy:

```caddyfile
untraded.example.com {
	# Demos players send go to the API directly (up to 400 MB; see below).
	handle /api/uploads {
		request_body {
			max_size 400MB
		}
		uri strip_prefix /api
		reverse_proxy 127.0.0.1:8000
	}
	reverse_proxy 127.0.0.1:3000
}
```

With Caddy itself in Docker, publish on the Docker bridge (`UNTRADED_BIND=172.17.0.1`) and use
`172.17.0.1` in both `reverse_proxy` lines. Set `UNTRADED_SITE_URL` to the same address. The web
(`UNTRADED_WEB_PORT`, 3000) and the API (`UNTRADED_API_PORT`, 8000) are published for the proxy
only; the worker and the database stay inside Compose.

The `/api/uploads` block matters for players on slow lines: the web relays it too, but Node
drops a request that takes more than 5 minutes to arrive (a 300 MB demo below about 8 Mbit/s).
Keep `max_size` in line with `UNTRADED_UPLOAD_MAX_MB`.

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
- For a demo a player sent: `unavailable` also when it was refused, with the reason in
  `match_source.rejected` (`not_a_demo`, `corrupt`, `too_large`, `unsupported_mode`,
  `not_a_player`).

## Data

| Volume | Holds | Back it up |
|---|---|---|
| `db-data` | PostgreSQL | through `backups` |
| `backups` | the daily dumps of the database (`daily/`, `weekly/`) | yes, off the machine (below) |
| `store` | raw demos (`demos/`) and Parquet per match (`matches/`) | the Parquet, at least: metrics are recomputed from it (ADR 0009) |
| `collector-data` | the bot's refresh token (`.state.json`, mode 600) | no: log in again instead |
| `uploads` | demos players sent, until the worker moves them to `store` (minutes) | no |

## Erasing a player

A player erases their account from their settings (`POST /me/erase`), or an admin erases them
(`DELETE /admin/players/{steam_id}`). Their account closes at once: signed out, and no longer
followed by the collector. The worker's `erase_player` job then deletes:

- their account, with their sources and encrypted codes, consents, votes, invitation and
  personal workspace;
- their play sessions, advice and aggregates;
- the matches no other user played in: rows, Parquet and raw demo.

The matches other users played in stay, as those users' matches. The erased player is then one
of the players there like anyone not registered, and is left out of the level references.
Copies outside the database follow their own rhythm: the daily dumps expire (4 weeks at most),
and an off-site copy you run keeps what you tell it to.

## Backups

The `backup` service dumps the database every day at 03:00 UTC (`pg_dump`, custom format) into
the `backups` volume, and keeps the last 7 daily dumps and 4 weekly ones. A dump on the same
machine does not survive the loss of that machine: copy the volume elsewhere (rsync over SSH, a
backup tool), together with the Parquet in `store` (`matches/`). Without the Parquet, the matches
cannot be recomputed.

```bash
docker compose logs backup                     # one "backup: untraded-YYYY-MM-DD.dump" per day
docker compose exec backup ls -l /backups/daily
```

To restore, into an empty database (a fresh `db-data` volume), before starting the services. The
API's role is not in the dump (roles belong to the server, not to the database): create it first.

```bash
docker compose up -d db
docker compose cp untraded-2026-10-21.dump db:/tmp/restore.dump
docker compose exec db psql -U untraded -c "CREATE ROLE untraded_api NOLOGIN"
docker compose exec db pg_restore -U untraded -d untraded --no-owner --exit-on-error /tmp/restore.dump
docker compose up -d
```

Keep `UNTRADED_SECRET_KEY` with your backups: without it, the authentication codes in the dump
cannot be decrypted, and every source has to be added again.

## Updating

```bash
git pull && docker compose up -d --build
```

`migrate` applies any new migration before the services start. After an update that adds or
changes the 2D viewer's round replays, write them for the matches parsed before:

```bash
docker compose exec worker untraded-worker replays
```
