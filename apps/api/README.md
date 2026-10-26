<!--
SPDX-FileCopyrightText: 2026 The Untraded Authors
SPDX-License-Identifier: AGPL-3.0-only
-->

# untraded-api

The HTTP API (FastAPI). AGPL-3.0-only. Steam sign-in, the signed-in player's matches, sessions
and their reports, the 2D viewer's round replays, what an invited player gives on the site
(consent, codes), the demos players send, erasure, and the admin's routes.

```bash
just db-up && just db-migrate
UNTRADED_PUBLIC_URL=http://localhost:8000 UNTRADED_WEB_URL=http://localhost:3000 uv run untraded-api
```

`untraded-api` listens on `127.0.0.1:8000` (`--host`, `--port`; the container uses `0.0.0.0`)
and trusts the reverse proxy's `X-Forwarded-*` headers.

| Variable | Default | Role |
|---|---|---|
| `UNTRADED_DATABASE_URL` | the `compose.dev.yaml` database | PostgreSQL |
| `UNTRADED_PUBLIC_URL` | `http://localhost:8000` | where browsers reach the API; Steam sends users back to `/auth/steam/callback` under it. `https` makes the cookie `Secure` |
| `UNTRADED_WEB_URL` | `http://localhost:3000` | where users land after signing in or out |
| `UNTRADED_SESSION_DAYS` | `30` | how long a sign-in lasts |
| `UNTRADED_ADMIN_STEAM_IDS` | unset (no admin) | SteamID64s of the admins, comma-separated: only they reach the `/admin` routes (403 otherwise) |
| `UNTRADED_CONSENT_VERSION` | `2` | the version of the consent text the site shows: a player agrees to this one, and again when it changes |
| `UNTRADED_SECRET_KEY` | unset | the collector's key (32 bytes, base64): encrypts the authentication code a player gives on the site. Unset, players cannot give their codes (503) |
| `STEAM_WEB_API_KEY` | unset | checks a player's codes with Steam before keeping them; unset, they are kept unchecked |
| `UNTRADED_BACKUPS_DIR` | unset | the `backup` service's dumps, read only, for `/admin/health` |
| `UNTRADED_STORE_DIR` | unset | the worker's store, read only, for the round replays; unset, every replay is a 404 |
| `UNTRADED_UPLOADS_DIR` | unset | where the demos players send are written, for the worker (`ingest_upload`); unset, uploads are off (503) |
| `UNTRADED_UPLOAD_MAX_MB` | `400` | the largest file a player may send |
| `UNTRADED_UPLOADS_PER_DAY` | `20` | uploads per player in 24 hours; `0` for no limit |
| `UNTRADED_UPLOADS_IN_FLIGHT` | `3` | a player's uploads not analysed yet; `0` for no limit |
| `UNTRADED_UPLOAD_MIN_FREE_GB` | `5` | uploads are refused while the uploads disk has less free space |

## Routes

| Route | |
|---|---|
| `GET /auth/steam` | redirects to Steam |
| `GET /auth/steam/callback` | checks Steam's answer with Steam (`check_authentication`), opens a session for a registered or invited account (an invitation becomes an account at its first sign-in), sets the cookie, redirects to the web (`?signin=not_invited` or `?signin=failed` otherwise) |
| `POST /auth/logout` | ends the session |
| `GET /me` | the signed-in user: admin or not, their current consent and the current text's version, their source (followed, last success, last error), and whether codes can be kept here (401 otherwise) |
| `POST /me/consent` | records the player's consent (`text_version`, `analysis` for box 1, `research_corpus` for box 2); 409 unless it names the current text. `analysis: false` withdraws it and pauses their sources |
| `PUT /me/source` | keeps the player's two codes (`auth_code`, `share_code`, found in what was pasted, put back in place if swapped) once Steam accepted them; the authentication code is stored encrypted. 409 without consent, 422 names the refused field, 503 when Steam does not answer or no key is set |
| `POST /me/erase` | `{"confirm": true}`: the player's right to erasure. The account closes at once (signed out, no longer followed), then the worker deletes their data (`erase_player`) |
| `GET /matches?limit=&offset=` | the matches the user may see, most recent first, with the user's team, result and headline numbers (20 by default, at most 100) |
| `GET /matches/{id}` | a match: score, rounds, players and their headline numbers (404 when not visible) |
| `GET /matches/{id}/players/{steam_id}` | every value metric of a player in that match, on the scopes `match`, `ct` and `t` |
| `GET /matches/{id}/rounds/{n}/replay?v=` | a round as the 2D viewer replays it (`docs/replay-format.md`), gzipped JSON the browser keeps for a day. `v` is the format the viewer reads: a replay in another version is a 404 that is not cached |
| `GET /sessions?limit=&offset=` | the user's play sessions, most recent first, with their record, maps, headline comparisons and first priority |
| `GET /sessions/{id}` | a session's report: its reference (own days, level or none), matches, up to three priorities with their evidence, the previous priorities' indicators since (follow-up), and every metric against the reference |
| `POST /advice/{id}/feedback` | useful (`{"vote": 1}`), not useful (`-1`) or take the vote back (`0`) on one of the user's priorities |
| `POST /uploads?name=&mode=&played_at=` | a demo the player sends, as the request body (`.dem`, `.dem.bz2`, `.dem.gz` or `.dem.zst`), streamed to the uploads directory and checked as it arrives. `mode` is `faceit`, `esea` or `scrim`; the worker recognises a demo from Valve's servers as Premier whatever the choice. 202 with its id, then the worker's `ingest_upload`. Refusals name their reason: `not_a_demo` (422), `too_large` (413), `disk_full` (507), `consent` (409), `quota` or `busy` (429); 503 when uploads are off |
| `GET /uploads` | the player's uploads of the last 30 days, newest first (`processing`, `ready`, `refused` or `failed`, with the reason), the largest file accepted, and why a new one would be refused, if it would |
| `GET /admin/players` | every player, newest first, with their state (`invited`, `joined`, `consented`, `followed`, `paused`, `withdrawn`), consent, source and matches |
| `POST /admin/invitations` | invites a Steam account (`steam_id`, `display_name`): its first sign-in creates the user |
| `DELETE /admin/invitations/{steam_id}` | withdraws an invitation not used yet |
| `DELETE /admin/players/{steam_id}` | erases a player as `POST /me/erase` does, invitation included (409 for the admin themself) |
| `POST /admin/sources/{id}/pause`, `POST /admin/sources/{id}/resume` | stops or resumes following a player |
| `DELETE /admin/sources/{id}` | stops following a player and deletes their encrypted code; their matches, account and access to the site stay |
| `GET /admin/health` | database size, jobs by status and the last failed ones, matches of the last 7 days by status, sources (total, paused, erroring), the newest dump and the off-site copy's `offsite.json` if any, free disk |
| `GET /health` | liveness |

## Security

- **Sign-in is by invitation** during the beta: the database opens a session only for a Steam
  account with a user or a pending invitation (`open_auth_session`, migrations 0002 and 0008).
  Admins invite from the site; the collector's `add-source` also creates a user.
- The cookie (`untraded_session`, `HttpOnly`, `SameSite=Lax`, `Secure` over https) holds a
  random token; the database keeps its sha256 only.
- Every request runs in one transaction as `untraded_api`, with `app.user_id` set: row-level
  security (ADR 0011) decides what it sees. The role reads; it writes only the player's own
  consent and votes, and the rest (their codes, uploads and erasure) through database functions
  limited to the player's own rows.
- The `/admin` routes are the exception: once the user is checked to be an admin, they run as the
  connection's own role, over every player.

## Tests

`uv run pytest apps/api`. The tests marked `db` need `UNTRADED_TEST_DATABASE_URL` (they empty
`app_user` and the match tables); CI runs them on PostgreSQL 16. Steam is replaced by a fake in
every test, and the match tests load the `premier-half` fixture as the worker would.

Steam ids are strings in JSON: they do not fit in a JavaScript number. Metric values are those
of the current version of each metric (`metric_current`), with the default parameters.
