# 0003. Versioned metric registry

- Status: Accepted
- Date: 2026-10-13

## Context

Transparency is the product's core promise: every number must have a public formula, and users must be able to tell which formula produced a stored value. Formulas will evolve.

## Decision

- Every metric is registered with a **stable ID** (e.g. `trade.untraded_deaths`), a **semantic version**, a unit, a scope (player×match, player×round, team×match), its dependencies, its parameters with defaults, and its documentation.
- Changing a formula **bumps the version**; stored results keep the version that produced them, and history can be recomputed.
- Metric documentation pages are **generated from the registry**; CI fails if they drift.
- `docs/metrics-v1.md` is the human-written spec for the first catalog.

## Consequences

- A metric PR always touches the spec, the code, the tests and (when outputs change) the golden files.
- Recomputing history requires keeping raw demos or full tick data (see ADR 0005).
