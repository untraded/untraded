# Contributing to Untraded

Thanks for your interest! The project is in alpha (phase 2, solo beta: see `docs/roadmap.md`). The metrics engine and the advice rules (`packages/untraded-py`) are the easiest places to help.

## Before you start

- Read `CLAUDE.md` (project rules, also valid for humans) and `docs/metrics-v1.md`. Each app under `apps/` has a README with how to run it; `apps/web/dev/mock_api.py` lets you work on the web app without a database.
- For anything larger than a small fix, open an issue first so we can agree on the approach.

## Workflow

1. Fork and create a branch: `feat/<short-topic>` or `fix/<short-topic>`.
2. `just install`, then make your change with tests.
3. `just check` must pass.
4. Use [Conventional Commits](https://www.conventionalcommits.org) for commit messages and PR titles.
5. Open a pull request. On your first PR, the CLA bot asks you to sign the [CLA](CLA.md) by posting a comment.

## Adding or changing a metric

A metric PR must include:

- the definition in `docs/metrics-v1.md` (or the next catalog version), with parameters and defaults;
- the implementation registered with a stable ID and a version (bump the version if the formula changes);
- unit tests on hand-built rounds, and an invariant test when one applies;
- which way is an improvement (`better`), its limits and version history (`untraded.metrics.notes`), its parameters (`untraded.metrics.params`);
- the generated pages refreshed with `just docs` (`docs/metrics/`);
- if the fixtures' values move on purpose, `just fixtures-expect` to rewrite their `expected_metrics.json`, with the diff explained in the PR.

## Licensing

- Files under `packages/` are MIT; everything else is AGPL-3.0-only. The radars (`apps/web/public/radars/`) are CC BY 4.0, and the name and logo are trademarks ([TRADEMARKS.md](TRADEMARKS.md)).
- Add the SPDX header to every new source file (see `CLAUDE.md`).
- `just check` runs `reuse lint` to verify it.
