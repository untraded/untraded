<!--
SPDX-FileCopyrightText: 2026 The Untraded Authors
SPDX-License-Identifier: AGPL-3.0-only
-->

# web

The web app (Next.js, React Server Components, Tailwind, PixiJS for the 2D viewer).
AGPL-3.0-only. In English and French.

```bash
pnpm --filter @untraded/web dev    # http://localhost:3000, with the API on http://localhost:8000
```

| Variable | Default | Role |
|---|---|---|
| `UNTRADED_API_INTERNAL_URL` | `http://localhost:8000` | how the web server reaches the API |
| `UNTRADED_SITE_URL` | unset | the site's address as browsers see it: the share image and the icons are linked from it |
| `UNTRADED_DISCORD_URL` | unset | an invitation link to the instance's Discord server (`https://discord.gg/...`), shown on the sign-in page; unset hides it |
| `UNTRADED_DEMO_STEAM_ID` | unset | the API's demo account (same value): set, the signed-out landing page offers the read-only demo (`/api/auth/demo`); unset hides the button |
| `UNTRADED_OPERATOR_NAME`, `UNTRADED_OPERATOR_EMAIL` | unset | the data controller and their contact, named in the consent text invited players agree to |
| `UNTRADED_HOSTING` | unset | where the data lives, as the consent text states it |
| `UNTRADED_DEMO_RETENTION_DAYS` | unset | the worker's raw demo retention, stated in the consent text (unset: kept; `0`: deleted once parsed) |
| `UNTRADED_TIME_ZONE` | `Europe/Paris` | time zone of dates and times until the player's browser sends its own (cookie `untraded_tz`, set on the first visit); an unknown IANA name falls back to the default |

## Pages

| Page | |
|---|---|
| `/` | signed out: the landing page, with sign-in with Steam (and why it failed, `?signin=`) and the demo when the instance has one. Signed in: the home page (the latest session and its priorities, what to work on before playing again, the previous priorities' progress, the matches still being analysed), or `/welcome` while something is missing |
| `/welcome` | an invited player's first steps: the consent text (box 1, box 2), then their two codes |
| `/sessions`, `/sessions/{id}` | the play sessions, and a session's report (the product's central screen): reference, priorities with their evidence and rounds to review, follow-up, every metric against the reference |
| `/matches`, `/matches/{id}` | the matches, and a match seen from the player: rounds, the rounds the priorities flag, their numbers on each side, both teams |
| `/matches/{id}/rounds/{n}` | the 2D viewer: one round replayed from above on our own radars (`public/radars/`), with its win-probability curve and swings (`?t=` the tick it opens on, `?player=` the player followed) |
| `/progress` | the player's key figures session after session against their reference (last 10 sessions, 30 days, 3 months or all), and the previous priorities |
| `/upload` | sending a demo (FACEIT, ESEA, a scrim, or a Premier match the bot missed), with what became of those of the last 30 days |
| `/formulas`, `/formulas/{id}` | every metric's formula, from `docs/metrics/` (read at run time, shipped in the image), with the player's last value |
| `/settings` | tone (coach or analyst), language, theme (system, light, dark), consent (read the text, change box 2, withdraw), codes (again when the collector fails), and erasure of the account |
| `/admin`, `/admin/health` | admins only: every player, from invited to followed (invite, withdraw an invitation, pause, resume or remove a source, erase), and how the server is doing (database, jobs and the last failed ones, collection, backups, disk) |

## How it works

- **Server first.** Pages call the API from the server and forward the session cookie. Forms
  (sign-out, language, tone, theme, votes, consent, codes, erasure, the admin's actions) are
  server actions. Client JavaScript is kept to what needs it: the upload form (progress bar),
  the 2D viewer, the charts, menus.
- **One origin.** The web relays `/api/*` to the API (`app/api/[...path]/route.ts`), redirects,
  cookies and streamed bodies included: the API's session cookie is the web's, and a reverse
  proxy only has to reach the web. The browser itself calls `/api` for the sign-in, the upload
  (`POST /api/uploads`) and the round replays. Run the API with `UNTRADED_PUBLIC_URL=<site>/api`
  and `UNTRADED_WEB_URL=<site>` (locally `http://localhost:3000/api` and
  `http://localhost:3000`). Behind a proxy, send `/api/uploads` to the API directly: see
  `docs/self-hosting.md`.
- **Languages.** No locale in the URL: the `untraded_locale` cookie (set by the switcher), else
  the browser's languages (`next-intl`, `messages/{en,fr}.json`). Every string goes through
  the messages. The other choices are cookies too: `untraded_tone`, `untraded_theme`,
  `untraded_sidebar`.

## Working without the API

`apps/web/dev/mock_api.py` mocks the API with invented, seeded data covering every screen: the
three kinds of reference, priorities with evidence, follow-up, matches in every status, uploads,
the admin pages, and round replays for the 2D viewer (from the `premier-half` fixture, with
`uv run`). Signing in goes straight through, with no Steam.

```bash
uv run python apps/web/dev/mock_api.py                     # http://127.0.0.1:8077 (MOCK_PORT)
UNTRADED_API_INTERNAL_URL=http://127.0.0.1:8077 MOCK_WEB_URL=http://localhost:3000   pnpm --filter @untraded/web dev
```

The signed-in player starts followed and admin. To see each onboarding screen, open
`/api/mock/state/<state>` on the site: `joined`, `consented`, `followed`, `error` (Valve refuses
their code), `withdrawn`, `outdated` (a newer consent text), `nokey` (the server cannot keep codes)
or `player` (not an admin). Codes that answer like Steam would: the auth code `XXXX-XXXXX-XXXX`
and the share code `CSGO-00000-00000-00000-00000-00000` are refused (422), and `STEA-MDOWN-0503`
stands for Steam not answering (503).

Uploads: `/api/mock/uploads/<refusal>` sets why a new demo would be refused (`off`, `disk_full`,
`consent`, `quota`, `busy`, or `none`). A demo sent is processed for 20 seconds, then its file
name decides what became of it: `notademo`, `corrupt`, `compet` (Competitive), `notme` (the
player is not in it) or `broken` (parsing failed); any other name becomes a match.

`pnpm test` covers the formatting, the language choice, onboarding, uploads, the replay and
win-probability helpers; `pnpm build` checks every page.
