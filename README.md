# Untraded

**Never die untraded.**

Untraded is an open-source, self-hostable Counter-Strike 2 analyzer and coach. It fetches your matches, parses the demos, and tells you — after every session — the one to three things to fix, with the rounds that prove it. Every metric has a public formula, and your data stays yours.

> **Status: alpha.** Phase 1 is done: the [`untraded`](packages/untraded-py) metrics engine and command line (`pip install untraded`) are usable, and validated against CS Demo Manager on 30 matches. Phase 2 (solo beta: collector, web app, advice) has started. See the [roadmap](docs/roadmap.md).

## Why

- **Explainable.** Every number has a documented, versioned formula. Our rating breaks down round by round.
- **Actionable.** At most three priorities per report, each with evidence rounds, a drill or in-game adjustment, and an indicator to track.
- **Built for high-level play and teams.** Premier, FACEIT, ESEA and scrims; team review and tactical stats are first-class.
- **Yours.** Self-host it with Docker Compose, query it with SQL, export everything.

## Repository layout

| Path | What | License |
|---|---|---|
| `packages/untraded-py` | Python metrics library ([`untraded` on PyPI](https://pypi.org/project/untraded/)) | MIT |
| `packages/untraded-js` | TypeScript helpers and shared types ([`untraded` on npm](https://www.npmjs.com/package/untraded)) | MIT |
| `apps/` | Collector and worker (phase 2); API, web app and FACEIT extension to come | AGPL-3.0-only |
| `db/` | Database migrations (`untraded-db`) | AGPL-3.0-only |
| `spikes/` | Throwaway phase 0 experiments, each with a report | AGPL-3.0-only |
| `corpus/` | Manifest of reference demos (the demos themselves are never committed) | AGPL-3.0-only |
| `docs/` | Roadmap, metric catalog, architecture decision records | AGPL-3.0-only |

Licensing follows the [REUSE](https://reuse.software) specification: every file declares its license.

## Self-hosting

`docker compose up -d --build` runs the ingestion chain: your Valve matches are collected, parsed and analysed into PostgreSQL. There is no web interface yet. See [docs/self-hosting.md](docs/self-hosting.md).

## Development

Requirements: Python 3.14, Node.js 22+, [uv](https://docs.astral.sh/uv/), [pnpm](https://pnpm.io), [just](https://just.systems). With [mise](https://mise.jdx.dev), `mise install` sets everything up. Linux, macOS and Windows are supported (on Windows, `just` runs recipes with PowerShell).

```bash
just install   # Python and TypeScript dependencies
just check     # lint, type-check, test, license check
```

## Contributing

Contributions are welcome, starting with the metrics engine. Read [CONTRIBUTING.md](CONTRIBUTING.md); a light [Contributor License Agreement](CLA.md) is signed through a pull request comment.

## Disclaimer

Untraded is not affiliated with Valve, HLTV, FACEIT or Leetify. Counter-Strike is a trademark of Valve Corporation.
