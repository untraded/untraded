# Spike S0.1 — Valve pipeline end to end

Question: can we go from a share code to a downloaded demo, unattended, every hour, for a week?

## Setup

1. Create a **secondary** Steam account for the bot (never your main account).
2. `cp .env.example .env` and fill it in. `.env` and `.state.json` are git-ignored; `.state.json` holds the bot refresh token (mode 600).
3. `pnpm install` at the repository root.

## Run

```bash
just spike-valve
```

The first run asks for a Steam Guard code, then stores a refresh token: later runs are unattended. Each run walks the share-code chain, asks the Game Coordinator for demo URLs, downloads `.dem.bz2` files into `$UNTRADED_CORPUS_DIR/inbox/`, and appends measurements to `out/matches.jsonl`.

Hourly cron entry (adapt paths):

```cron
7 * * * * cd /path/to/untraded && PATH=$HOME/.local/bin:$PATH just spike-valve >> spikes/S0.1-valve/out/cron.log 2>&1
```

## Run in Docker (Portainer, any server, amd64 or arm64)

`compose.yaml` runs the spike every hour in a container; demos, bot state and logs live in the `spike-valve-data` volume (`/data`).

1. Run the spike once locally (`just spike-valve`) to get a refresh token: it is the `botRefreshToken` value in `.state.json`.
2. Deploy `spikes/S0.1-valve/compose.yaml` (Portainer: *Stacks → Add stack → Repository*, or `docker compose up -d --build` in this directory) with these variables: `STEAM_WEB_API_KEY`, `PLAYER_STEAMID64`, `PLAYER_AUTH_CODE`, `BOT_ACCOUNT_NAME`, `BOT_REFRESH_TOKEN` and `PLAYER_INITIAL_SHARE_CODE` (the `knownShareCode` of your local `.state.json`, so already downloaded matches are skipped).
3. Stop the local schedule: the same bot account must not run in two places.

Logs: `docker compose logs -f` (or the container logs in Portainer). Measurements: `/data/out/matches.jsonl` in the volume.

## What we measure

- delay between match end and demo availability (`minutesSinceEnd`);
- Game Coordinator connection and request times, failures, timeouts;
- download size and duration; expired demos (HTTP 404/502);
- share-code chain errors (412: code older than a month, 403: bad auth code).

Findings go to `RAPPORT.md`.
