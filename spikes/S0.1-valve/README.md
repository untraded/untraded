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

## What we measure

- delay between match end and demo availability (`minutesSinceEnd`);
- Game Coordinator connection and request times, failures, timeouts;
- download size and duration; expired demos (HTTP 404/502);
- share-code chain errors (412: code older than a month, 403: bad auth code).

Findings go to `RAPPORT.md`.
