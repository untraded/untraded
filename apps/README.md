# Apps

Product services, all AGPL-3.0-only, built in phase 2 (see `docs/roadmap.md`). `compose.yaml` runs them together ([docs/self-hosting.md](../docs/self-hosting.md)); each app has its own README.

| App | Language | Role |
|---|---|---|
| [`collector`](collector/) | TypeScript | Follows players' Valve matches (Premier): Steam share-code chain, Game Coordinator bot, one `download` job per new match |
| [`worker`](worker/) | Python | Consumes the PostgreSQL job queue and runs the `untraded` library: `download`, `ingest_upload` (demos players send), `parse` (tables, metrics, round replays, swings), `session` (reports and advice), `erase_player`; also references by level and raw demo retention |
| [`api`](api/) | Python (FastAPI) | Steam sign-in by invitation, under row-level security: matches, round replays, sessions, advice feedback, demo uploads, consent, erasure, admin |
| [`web`](web/) | TypeScript (Next.js, Tailwind, shadcn/ui, PixiJS) | The site, in English and French: home, matches, match page, 2D round viewer, session reports, progress, formulas, demo upload, settings, onboarding and admin. It relays `/api/*` to the API |

The database migrations live in `db/` (`untraded-db`).

Not built yet: Renown polling in the collector and the FACEIT browser extension (phase 2), the scrim webhook for MatchZy (phase 3). Phase 0 prototypes live in `spikes/`.
