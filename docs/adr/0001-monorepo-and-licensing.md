# 0001. Monorepo and licensing

- Status: Accepted
- Date: 2026-10-13

## Context

Untraded spans Python (parsing, metrics, API, worker) and TypeScript (Steam collector, web app, browser extension). The product must stay open source while a hosted commercial version is planned within 12 months. Metric formulas should be reusable anywhere, including notebooks and other tools.

## Decision

- One repository, `untraded/untraded`, with a **uv** workspace for Python and a **pnpm** workspace for TypeScript, orchestrated by **just**.
- `packages/*` (reusable libraries, published as `untraded` on PyPI and npm) are **MIT**.
- Everything else (apps, spikes, docs, infra) is **AGPL-3.0-only**: a modified hosted version must publish its source.
- Licensing follows the **REUSE** specification: SPDX headers in source files, `REUSE.toml` for the rest, checked in CI.
- External contributions require a light **CLA** (CLA Assistant Lite), keeping dual-licensing possible.
- Packages are released by **trusted publishing (OIDC)** from GitHub Actions; no registry token is stored.

## Consequences

- One `just check` validates the whole repository; cross-language changes land in one PR.
- Contributors must add SPDX headers; `reuse lint` fails the build otherwise.
- The CLA adds a small step on a contributor's first PR.
