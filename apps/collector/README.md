<!--
SPDX-FileCopyrightText: 2026 The Untraded Authors
SPDX-License-Identifier: AGPL-3.0-only
-->

# collector

Follows players' Valve matches (Premier) and queues their demos for the worker. AGPL-3.0-only.
The proper version of spike S0.1.

Each round, for each enabled `ingest_source` of kind `valve_bot` whose player's account is not
being erased:

1. walks the player's share-code chain from the last known code (Steam Web API,
   `GetNextMatchSharingCode`), at most `MAX_MATCHES_PER_RUN` new codes;
2. asks the Game Coordinator, through a bot account, for each new match's demo URL (the bot
   asks for the free CS2 license itself if it does not own it);
3. records the match (`match`, `match_source`) and its `download` job in one transaction, and
   moves the known code forward. The worker downloads, parses and analyses it. A match Valve has
   no demo for is recorded `unavailable`, without a job.

A match another followed player already brought is not asked again. A failure on a match keeps
the known code before it, so the next round retries it. A broken chain (412: code older than a
month, 403: wrong authentication code) is recorded in `ingest_source.last_error`.

The chain also holds Competitive and Wingman matches: their mode is only known from the demo,
so the worker checks it and sets them aside.

## Commands

```bash
pnpm start login        # once: logs the bot in (asks for Steam Guard) and keeps its refresh token
pnpm start add-source --steam-id 7656119... --name me --share-code CSGO-...
pnpm start run          # a round every COLLECTOR_INTERVAL_SECONDS; --once for a single round
```

`add-source` creates the player's user and personal workspace if needed, which also lets them
sign in to the site, and asks for the match history authentication code on the terminal (or
reads `PLAYER_AUTH_CODE`). Players invited from the site give their codes there instead: the
API creates the same source, encrypted with the same key.

### Consent

When you follow other players, record what they agreed to. The text is yours to write; a record
names its version. Box 1 (analysis) is required to follow a player, box 2 (research corpus) is
optional: only the demos of players who ticked it may be kept beyond the retention period. On
the site, players agree themselves (to the text `UNTRADED_CONSENT_VERSION` of the API names),
and cannot give their codes before box 1.

```bash
pnpm start add-source --steam-id 7656119... --name p1 --share-code CSGO-... --text-version 1 --corpus
pnpm start consent --steam-id 7656119... --text-version 2            # box 1 only
pnpm start consent --steam-id 7656119... --withdraw                  # then remove-source
```

Each record is a new row of `consent`, never changed, so the history stays; a player's consent
is their latest one (`consent_current`). `sources` shows it. The collector does not check it
when it collects: `consent --withdraw` does not stop following the player, so run
`remove-source` (or `pause-source`) after it. Withdrawing on the site pauses their source.

### Managing the followed players

To manage the followed players (`--source <id>`, or `--steam-id` when the player has one source):

```bash
pnpm start sources                                       # id, player, state, known code, last round, error
pnpm start update-source --steam-id 7656119... --share-code CSGO-...  # restart the chain there
pnpm start update-source --steam-id 7656119... --auth-code            # asks for a new authentication code
pnpm start pause-source --steam-id 7656119...            # resume-source to follow them again
pnpm start remove-source --steam-id 7656119... --yes
```

`sources` never prints authentication codes. A new share code or authentication code clears the
source's last error, so the next round tries it: that is the fix for a broken chain (412: the
known code is more than a month old; 403: the player changed their authentication code).
`remove-source` deletes the source and its encrypted code; the player's matches, user and access
to the site stay. Admins can also pause, resume and remove a source from the site's admin page.

| Variable | Role |
|---|---|
| `UNTRADED_DATABASE_URL` | PostgreSQL (default: the `compose.dev.yaml` database) |
| `UNTRADED_SECRET_KEY` | 32 bytes, base64: encrypts the authentication codes in the database |
| `STEAM_WEB_API_KEY` | Steam Web API key (from the maintainer's main account, never the bot's) |
| `BOT_ACCOUNT_NAME`, `BOT_PASSWORD` | the bot account; the password is only needed by `login` |
| `BOT_REFRESH_TOKEN` | seeds the state when the data directory is empty (a container cannot prompt) |
| `COLLECTOR_DATA_DIR` | holds `.state.json` with the refresh token (mode 600; default `data`) |
| `PLAYER_AUTH_CODE` | the authentication code for `add-source` and `update-source --auth-code`, instead of the prompt |
| `COLLECTOR_INTERVAL_SECONDS` | time between rounds (3600 by default) |
| `MAX_MATCHES_PER_RUN` | new matches per player and round (20 by default) |

Secrets never go into git. The spike's `.state.json` works as is: copy it into the data
directory.

## Secrets in the database

`ingest_source.secret`: version byte `1`, 12-byte nonce, AES-256-GCM ciphertext, 16-byte tag,
with the source id as additional authenticated data (`src/secrets.ts`). The API uses the same
format and key for the codes players give on the site (`untraded_api.secrets_box`).

## Tests

`pnpm test`. The database tests need `UNTRADED_TEST_DATABASE_URL` (they empty the tables they
use); CI runs them on PostgreSQL 16.
