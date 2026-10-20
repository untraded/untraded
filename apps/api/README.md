<!--
SPDX-FileCopyrightText: 2026 The Untraded Authors
SPDX-License-Identifier: AGPL-3.0-only
-->

# untraded-api

The HTTP API (FastAPI). AGPL-3.0-only. So far: Steam sign-in and the signed-in user; matches
and session reports come next.

```bash
just db-up && just db-migrate
UNTRADED_PUBLIC_URL=http://localhost:8000 UNTRADED_WEB_URL=http://localhost:3000 uv run untraded-api
```

| Variable | Default | Role |
|---|---|---|
| `UNTRADED_DATABASE_URL` | the `compose.dev.yaml` database | PostgreSQL |
| `UNTRADED_PUBLIC_URL` | `http://localhost:8000` | where browsers reach the API; Steam sends users back to `/auth/steam/callback` under it. `https` makes the cookie `Secure` |
| `UNTRADED_WEB_URL` | `http://localhost:3000` | where users land after signing in or out |
| `UNTRADED_SESSION_DAYS` | `30` | how long a sign-in lasts |

## Routes

| Route | |
|---|---|
| `GET /auth/steam` | redirects to Steam |
| `GET /auth/steam/callback` | checks Steam's answer with Steam (`check_authentication`), opens a session for an invited account, sets the cookie, redirects to the web (`?signin=not_invited` or `?signin=failed` otherwise) |
| `POST /auth/logout` | ends the session |
| `GET /me` | the signed-in user (401 otherwise) |
| `GET /health` | liveness |

## Security

- **Sign-in is by invitation** during the beta: the database opens a session only for a Steam
  account with a user (`open_auth_session`, migration 0002). Users are added with the
  collector's `add-source` for now.
- The cookie (`untraded_session`, `HttpOnly`, `SameSite=Lax`, `Secure` over https) holds a
  random token; the database keeps its sha256 only.
- Every request runs in one transaction as `untraded_api`, with `app.user_id` set: row-level
  security (ADR 0011) decides what it sees, and the role can write nothing.

## Tests

`uv run pytest apps/api`. The tests marked `db` need `UNTRADED_TEST_DATABASE_URL` (they empty
`app_user`); CI runs them on PostgreSQL 16. Steam is replaced by a fake in every test.
