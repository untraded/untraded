# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The advice engine: rules, their evidence, what they cost, and the priorities.

A rule watches one metric. It fires when the session is worse than the reference by at least
`advice.min_gap_pct` (relative, in the metric's `better` direction) **and** the session holds at
least `advice.min_events` events that prove it. Its evidence is the very events the metric
counts (deaths, opportunities, flashes...), with the match, round and tick of each, so a player
can open them in the demo. Pattern rules (`history=True`) look at the session and the days
before it together, such as a zone where the player keeps dying.

A finding costs the rounds it touches, weighted by those the team lost: `rounds_lost +
advice.won_round_weight * (rounds_touched - rounds_lost)`. The open rating (phase 2, step 5)
replaces this estimate.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import polars as pl

from untraded.metrics import REGISTRY, Dataset
from untraded.metrics.registry import ParamValue

Family = Literal["trade", "duel", "clutch", "pos", "util", "eco", "combat"]
Evidence = Callable[[Dataset, int, Mapping[str, ParamValue]], pl.DataFrame]
"""The events proving a rule for one player: at least `match_id`, `round`, `tick`; any other
column is a detail shown with the event (distance, zone, items...)."""

DEFAULTS: dict[str, ParamValue] = {
    "advice.min_gap_pct": 15.0,
    "advice.min_events": 3,
    "advice.won_round_weight": 0.25,
}
"""⚙ Defaults of every rule, overridden per rule. To calibrate on the testers' sessions."""

EVIDENCE_COLUMNS = ("match_id", "round", "tick", "map", "side")


@dataclass(frozen=True)
class Rule:
    id: str
    """Stable, e.g. `trade.untraded_deaths`. Never changes, even when the version does."""
    version: str
    """Semantic version: a change of trigger or evidence bumps it (as for metrics, ADR 0003)."""
    family: Family
    metric: str
    """The metric the rule watches; its direction (`better`) says what "worse" is."""
    evidence: Evidence = field(repr=False)
    actions: tuple[str, ...]
    """Action ids (exercises, workshop maps, game adjustments), rendered by the clients."""
    params: Mapping[str, ParamValue] = field(default_factory=dict)
    """Overrides of `DEFAULTS` (`advice.*`). The evidence also gets the watched metric's own
    parameters, so the events are counted exactly as the metric counts them."""
    history: bool = False
    """A pattern over the session and the days before it, instead of a comparison."""
    indicator: str | None = None
    """The metric to follow in the next sessions (default: `metric`)."""

    @property
    def message_key(self) -> str:
        return f"advice.{self.id}"

    def param(self, name: str) -> ParamValue:
        return self.params.get(name, DEFAULTS[name])

    def evidence_params(
        self, overrides: Mapping[str, ParamValue] | None = None
    ) -> dict[str, ParamValue]:
        """The metric's parameters (defaults, then `overrides` such as a user's settings)."""
        defaults = REGISTRY[self.metric].params
        return {k: (overrides or {}).get(k, v) for k, v in defaults.items()}


RULES: dict[str, Rule] = {}


def rule(rule: Rule) -> Rule:
    """Registers a rule."""
    if rule.id in RULES:
        raise ValueError(f"rule {rule.id!r} registered twice")
    if rule.metric not in REGISTRY:
        raise ValueError(f"rule {rule.id!r} watches an unknown metric {rule.metric!r}")
    if not rule.history and REGISTRY[rule.metric].better == "neutral":
        raise ValueError(f"rule {rule.id!r} compares a neutral metric")
    RULES[rule.id] = rule
    return rule


@dataclass(frozen=True)
class Finding:
    rule: str
    rule_version: str
    metric: str
    metric_version: str
    basis: str
    session: float | None
    reference: float | None
    evidence: pl.DataFrame
    rounds_touched: int
    rounds_lost: int
    cost: float
    message_key: str
    actions: tuple[str, ...]
    indicator: str
    details: Mapping[str, Any] = field(default_factory=dict)
    """Values for the message beyond the comparison (a zone, a map...)."""

    @property
    def events(self) -> int:
        return self.evidence.height


def worse(rule: Rule, session: float | None, reference: float | None) -> bool:
    """Whether the session is worse than the reference by at least the rule's gap."""
    if session is None or reference is None:
        return False
    gap = float(rule.param("advice.min_gap_pct")) / 100
    if REGISTRY[rule.metric].better == "higher":
        return session < reference - abs(reference) * gap
    return session > reference + abs(reference) * gap


def placed(ds: Dataset, rows: pl.DataFrame, player: int, column: str) -> pl.DataFrame:
    """The player's rows (column `column`) in their kept rounds, with the map and side."""
    mine = rows.filter(pl.col(column) == player)
    keys = ds.played.filter(pl.col("steamid") == player).select("match_id", "round", "map", "side")
    return mine.join(keys, on=["match_id", "round"]).with_columns(
        pl.col("side").cast(pl.String), pl.col("tick").cast(pl.Int32)
    )


def standard(rows: pl.DataFrame, details: Sequence[str] = ()) -> pl.DataFrame:
    """Evidence columns first, then the details, sorted in the order they happened."""
    return rows.select(*EVIDENCE_COLUMNS, *details).sort("match_id", "round", "tick")


def _cost(rule: Rule, ds: Dataset, player: int, evidence: pl.DataFrame) -> tuple[int, int, float]:
    touched = evidence.select("match_id", "round").unique()
    outcome = (
        ds["round_player"]
        .filter(pl.col("steamid") == player)
        .select("match_id", "round", "team_won")
    )
    lost = touched.join(outcome, on=["match_id", "round"]).filter(~pl.col("team_won")).height
    weight = float(rule.param("advice.won_round_weight"))
    return touched.height, lost, lost + weight * (touched.height - lost)


def finding(
    rule: Rule,
    ds: Dataset,
    player: int,
    evidence: pl.DataFrame,
    *,
    basis: str,
    session: float | None,
    reference: float | None,
    details: Mapping[str, Any] | None = None,
) -> Finding:
    touched, lost, cost = _cost(rule, ds, player, evidence)
    return Finding(
        rule=rule.id,
        rule_version=rule.version,
        metric=rule.metric,
        metric_version=REGISTRY[rule.metric].version,
        basis=basis,
        session=session,
        reference=reference,
        evidence=evidence,
        rounds_touched=touched,
        rounds_lost=lost,
        cost=cost,
        message_key=rule.message_key,
        actions=rule.actions,
        indicator=rule.indicator or rule.metric,
        details=dict(details or {}),
    )


def prioritize(findings: Iterable[Finding], limit: int = 3, overlap: float = 0.5) -> list[Finding]:
    """The `limit` costliest findings. A finding whose rounds mostly repeat those of a finding
    already kept (more than `overlap` of them) is skipped: two rules on the same deaths make one
    priority, not two."""
    kept: list[Finding] = []
    for candidate in sorted(findings, key=lambda f: (-f.cost, -f.events, f.rule)):
        rounds = set(candidate.evidence.select("match_id", "round").iter_rows())
        if any(
            len(rounds & set(k.evidence.select("match_id", "round").iter_rows()))
            > overlap * len(rounds)
            for k in kept
        ):
            continue
        kept.append(candidate)
        if len(kept) == limit:
            break
    return kept
