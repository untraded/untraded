# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Advice: up to three priorities per session, each proved by rounds (vision § 5).

    findings = find(session, player, comparison, history=history)
    priorities = prioritize(findings)

`comparison` holds, per value metric, the session's value and the reference's, as
`untraded.reference.compare_to_self` returns them (`metric`, `basis`, `session`, `reference`);
another reference (players of the same level) has the same shape. `history` is the session plus
the days before it, for pattern rules. Rules are open, like the metrics: `RULES`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import polars as pl

from untraded.advice import rules as _rules  # noqa: F401 (registers the rules)
from untraded.advice.engine import DEFAULTS, RULES, Finding, Rule, finding, prioritize, worse
from untraded.metrics import Dataset
from untraded.metrics.registry import ParamValue

__all__ = ["DEFAULTS", "RULES", "Finding", "Rule", "find", "prioritize"]


def find(
    session: Dataset,
    player: int,
    comparison: pl.DataFrame,
    *,
    history: Dataset | None = None,
    params: Mapping[str, ParamValue] | None = None,
    rules: Iterable[Rule] | None = None,
) -> list[Finding]:
    """Every rule that fires for `player` in `session`, with its evidence and cost.

    `params` overrides metric parameters (e.g. the trade window) for the evidence.
    """
    reference = {row["metric"]: row for row in comparison.iter_rows(named=True)}
    in_session = set(session.played["match_id"].unique())
    found: list[Finding] = []
    for rule in rules if rules is not None else RULES.values():
        p = rule.evidence_params(params)
        minimum = int(rule.param("advice.min_events"))
        if rule.history:
            if history is None:
                continue
            pattern = rule.evidence(history, player, p)
            here = pattern.filter(pl.col("match_id").is_in(in_session))
            if here.height < minimum:
                continue
            # One spot per finding: the one where the session's events concentrate.
            spot = here.group_by("map", "side", "zone").len().sort("len", descending=True).row(0)
            keys = {"map": spot[0], "side": spot[1], "zone": spot[2]}
            same = (
                (pl.col("map") == spot[0])
                & (pl.col("side") == spot[1])
                & (pl.col("zone") == spot[2])
            )
            found.append(
                finding(
                    rule,
                    session,
                    player,
                    here.filter(same),
                    basis="pattern",
                    session=None,
                    reference=None,
                    details={**keys, "history_events": pattern.filter(same).height},
                )
            )
            continue
        row = reference.get(rule.metric)
        if row is None or not worse(rule, row["session"], row["reference"]):
            continue
        events = rule.evidence(session, player, p)
        if events.height < minimum:
            continue
        found.append(
            finding(
                rule,
                session,
                player,
                events,
                basis=row["basis"],
                session=row["session"],
                reference=row["reference"],
            )
        )
    return found
