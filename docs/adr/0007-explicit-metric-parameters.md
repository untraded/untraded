# 0007. Explicit metric parameters

- Status: Accepted; refined by [0010](0010-reference-data-and-corpus.md)
- Date: 2026-10-13
- Note (2026-10-26): ADR 0010 replaced the pro corpus of the last point: 🎯 defaults are calibrated on consenting players' demos.

## Context

Many CS metrics hide arbitrary thresholds: trade windows (2, 3 or 5 seconds depending on the tool), distances for "trade opportunity" or "isolated death", flash duration thresholds, economy buy-type limits. Hidden thresholds are exactly what makes competing tools opaque.

## Decision

- Every threshold is a **named parameter** with a documented default (e.g. `trade.window_s = 5.0`).
- Results record the parameter values used; changing a default bumps the metric version (ADR 0003).
- Common alternatives can be computed side by side (e.g. trades with a 3 s window under a `_w3` suffix).
- Defaults marked "to calibrate" in the spec are tuned on the pro corpus during phase 1.

## Consequences

- Users and coaches can reproduce and challenge any number.
- The parameter space must stay small and documented; adding a parameter requires a stated reason.
