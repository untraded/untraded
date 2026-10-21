<!--
SPDX-FileCopyrightText: 2026 The Untraded Authors
SPDX-License-Identifier: AGPL-3.0-only
-->

# web

The web app (Next.js, React Server Components, Tailwind). AGPL-3.0-only. So far: sign-in with
Steam, the session reports (the product's central screen), the match list and the match page, in
English and French.

```bash
pnpm --filter @untraded/web dev    # http://localhost:3000, with the API on http://localhost:8000
```

| Variable | Default | Role |
|---|---|---|
| `UNTRADED_API_INTERNAL_URL` | `http://localhost:8000` | how the web server reaches the API |
| `UNTRADED_OPERATOR_NAME`, `UNTRADED_OPERATOR_EMAIL` | unset | the data controller and their contact, named in the consent text invited players agree to |
| `UNTRADED_HOSTING` | unset | where the data lives, as the consent text states it |
| `UNTRADED_DEMO_RETENTION_DAYS` | unset | the worker's raw demo retention, stated in the consent text (unset: kept; `0`: deleted once parsed) |
| `UNTRADED_TIME_ZONE` | `Europe/Paris` | time zone of dates and times until the player's browser sends its own (cookie `untraded_tz`, set on the first visit); an unknown IANA name falls back to the default |

- **Server-side only.** Pages call the API from the server and forward the session cookie; the
  browser never talks to the API except to sign in. Sign-out and the language switch are
  server actions: the pages need no client JavaScript.
- **One origin.** The web relays `/api/*` to the API (`app/api/[...path]/route.ts`), redirects
  and cookies included: the API's session cookie is the web's, and a reverse proxy only has to
  reach the web. Run the API with `UNTRADED_PUBLIC_URL=<site>/api` and `UNTRADED_WEB_URL=<site>`
  (locally `http://localhost:3000/api` and `http://localhost:3000`).
- **Languages.** No locale in the URL: the `untraded_locale` cookie (set by the switcher), else
  the browser's languages (`next-intl`, `messages/{en,fr}.json`). Every string goes through
  the messages.

## Working without the API

`apps/web/dev/mock_api.py` mocks the API with invented, seeded data covering every screen: the three kinds of reference, priorities with evidence, follow-up, and matches in every status. Signing in goes straight through, with no Steam.

```bash
uv run python apps/web/dev/mock_api.py                     # http://127.0.0.1:8077
UNTRADED_API_INTERNAL_URL=http://127.0.0.1:8077 MOCK_WEB_URL=http://localhost:3000   pnpm --filter @untraded/web dev
```

The signed-in player starts followed and admin. To see each onboarding screen, open
`/api/mock/state/<state>` on the site: `joined`, `consented`, `followed`, `error` (Valve refuses
their code), `withdrawn`, `outdated` (a newer consent text), `nokey` (the server cannot keep codes)
or `player` (not an admin). Codes that answer like Steam would: the auth code `XXXX-XXXXX-XXXX`
and the share code `CSGO-00000-00000-00000-00000-00000` are refused (422), and `STEA-MDOWN-0503`
stands for Steam not answering (503).

`pnpm test` covers the formatting and the language choice; `pnpm build` checks every page.
