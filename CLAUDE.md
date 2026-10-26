# CLAUDE.md

Guidance for AI coding assistants (and humans) working in this repository.

## Project

Untraded: open-source, self-hostable CS2 demo analyzer and coach. Phases 0 (de-risking spikes) and 1 (metrics engine and CLI) are done; current phase: **2 (solo beta)**, with the collector, worker, API and web app running together in `compose.yaml`. Public roadmap: `docs/roadmap.md`. Metric spec: `docs/metrics-v1.md`. Advice rules: `docs/advice.md`. Win-probability model: `docs/winprob.md`. Replay format: `docs/replay-format.md`. Self-hosting: `docs/self-hosting.md`. Architecture decisions: `docs/adr/`.

## Layout

- `packages/untraded-py/` — Python library and CLI (parsing, metrics, references, advice rules, win-probability model, replays, radars), published as `untraded` on PyPI. **MIT.**
- `packages/untraded-js/` — TypeScript helpers, published as `untraded` on npm. **MIT.**
- `apps/` — product services: `collector` (TypeScript, Valve matches), `worker` (Python, job queue), `api` (FastAPI), `web` (Next.js). **AGPL-3.0-only.**
- `db/` — Alembic migrations (`untraded-db`); the schema is owned by Python (ADR 0006). **AGPL-3.0-only.**
- `docs/metrics/` — generated metric pages (`just docs`); never edit by hand.
- `spikes/` — throwaway phase 0 code; each spike ends with a `RAPPORT.md` (maintainer notes are in French, historical: do not rewrite them).
- `corpus/manifest.toml` — reference demos (files live in `$UNTRADED_CORPUS_DIR`, never in git).

## Commands

```bash
just install    # uv sync + pnpm install
just check      # everything CI runs: lint, format check, types, tests, REUSE
just fmt        # auto-format Python and TypeScript
just test       # tests only
just db-up      # development PostgreSQL (compose.dev.yaml); just db-migrate applies the migrations
```

Run `just check` before every commit.

## Rules

1. **English** for code, comments, docs and commit messages. UI strings go through i18n: every string in `apps/web/messages/en.json` and `fr.json`.
2. **SPDX header on every source file**: `SPDX-License-Identifier: MIT` under `packages/`, `AGPL-3.0-only` elsewhere, plus `SPDX-FileCopyrightText: 2026 The Untraded Authors`. Exceptions are annotated in `REUSE.toml`: the radars (`apps/web/public/radars/`) are `CC-BY-4.0`, and the logo files are `LicenseRef-Untraded-Trademark` (never AGPL or MIT; see `TRADEMARKS.md`). Do not add Valve's radar images (`docs/replay-format.md`).
3. **Conventional Commits** (`feat(metrics): …`, `fix(parsing): …`, `docs: …`, `chore: …`). One topic per PR.
4. **Metrics** (see ADR 0003 and 0007):
   - every metric has a stable ID, a semantic version, a written definition, explicit parameters with defaults, which way is an improvement (`better`), and tests;
   - changing a formula bumps the metric version; never change behaviour silently;
   - definitions in `docs/metrics-v1.md` are the spec — update the spec and the code in the same PR;
   - `docs/metrics/` is generated (pages, parameters, examples on the `premier-half` fixture): run `just docs` after a metric change. `just fixtures-expect` rewrites the fixtures' `expected_metrics.json` (the non-regression guard): run it only for an intended change, bump the versions of the metrics that moved, and explain the diff. Limits and version history live in `untraded.metrics.notes`, parameters in `untraded.metrics.params`.
5. **Parser isolation** (ADR 0002): only `untraded.parsing` may import `demoparser2`. Everything else works on canonical Polars tables. pandas never leaves the adapter.
6. **Never assume the tickrate.** Compute it from the demo (the header does not carry it); convert ticks to seconds explicitly.
7. **Rounds come from game state, events are optional** (ADR 0008): cut rounds with the game rules props, check `list_game_events()` per demo, and use the documented fallbacks when an event is missing.
8. **No secrets, demos or personal data in git.** `.env` files are ignored; demos stay in `$UNTRADED_CORPUS_DIR`. Test fixtures must be anonymized canonical extracts.
9. **Quality bar is high everywhere**: `mypy --strict` and TypeScript `strict` pass with zero errors; new code comes with tests. Spikes are the only exception (ruff and Biome still apply).
10. Prefer small, reviewable changes. Do not add dependencies without a reason stated in the PR.

## Domain notes

- Valve matchmaking demos expire ~30 days after the match; copy useful ones into the corpus immediately.
- Share-code chain: `GetNextMatchSharingCode` returns 200/202/412/403/429/503. A 412 means the known code is invalid or older than a month — ask the user for a new one.
- Demo URLs require a Game Coordinator session (`steam-user` + `globaloffensive`).
- HLTV Rating 3.0 is not public: never present an approximation as "HLTV Rating". Label 2.0 as "approx.".
