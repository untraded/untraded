# Apps

Product services, all AGPL-3.0-only. They arrive in phase 2 (see `docs/roadmap.md`):

| App | Language | Role |
|---|---|---|
| `collector` | TypeScript | Steam share-code chain, Game Coordinator bot pool, Renown polling, scheduling |
| `extension` | TypeScript | Browser extension sending FACEIT demos from the match room |
| `worker` | Python | Consumes the job queue, runs the `untraded` library (in progress: queue, store, loop) |
| `api` | Python (FastAPI) | REST API, Steam OpenID login, ingestion endpoints (uploads, MatchZy webhook) |
| `web` | TypeScript (Next.js, Tailwind, shadcn/ui) | Web app and PWA |

Phase 0 prototypes live in `spikes/`.
