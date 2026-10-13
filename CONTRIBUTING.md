# Contributing to Untraded

Thanks for your interest! The project is pre-alpha; the metrics engine (phase 1) is the best place to help.

## Before you start

- Read `CLAUDE.md` (project rules, also valid for humans) and `docs/metrics-v1.md`.
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
- updated golden files if outputs change, with an explanation in the PR.

## Licensing

- Files under `packages/` are MIT; everything else is AGPL-3.0-only.
- Add the SPDX header to every new source file (see `CLAUDE.md`).
- `just check` runs `reuse lint` to verify it.
