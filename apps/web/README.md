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
| `TZ` | the host's | time zone of the dates and times (pages render on the server) |

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

`pnpm test` covers the formatting and the language choice; `pnpm build` checks every page.
