# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The advice engine: rules, their evidence, what they cost, and the priorities.

A rule watches one metric. It fires when the session is worse than the reference by at least
`advice.min_gap_pct` (relative, in the metric's `better` direction), the session holds at least
`advice.min_events` events that prove it, **and** chance alone rarely gives that many events at the
reference's rate (`chance` below `advice.max_chance`). Below `advice.strong_chance`, the finding is
a clear signal and goes first. Its evidence is the very events the metric counts (deaths,
opportunities, flashes...), with the match, round and tick of each, so a player can open them in
the demo. Pattern rules (`history=True`) look at the session and the days before it together, such
as a zone where the player keeps dying.

A finding costs the rounds it touches, weighted by those the team lost: `rounds_lost +
advice.won_round_weight * (rounds_touched - rounds_lost)`. The open rating (phase 2, step 5)
replaces this estimate.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from math import exp, lgamma, log
from typing import Any, Literal

import polars as pl

from untraded.metrics import REGISTRY, Dataset, compute
from untraded.metrics.registry import ROUNDS, ParamValue

Family = Literal["trade", "duel", "clutch", "pos", "util", "eco", "combat"]
Evidence = Callable[[Dataset, int, Mapping[str, ParamValue]], pl.DataFrame]
"""The events proving a rule for one player: at least `match_id`, `round`, `tick`; any other
column is a detail shown with the event (distance, zone, items...)."""

DEFAULTS: dict[str, ParamValue] = {
    "advice.min_gap_pct": 15.0,
    "advice.min_events": 3,
    "advice.won_round_weight": 0.25,
    "advice.max_chance": 0.2,
    "advice.strong_chance": 0.05,
}
"""⚙ Defaults of every rule, overridden per rule. To calibrate on the testers' sessions."""

EVIDENCE_COLUMNS = ("match_id", "round", "tick", "map", "side")

PRIORITIES = 3
"""How many findings of a session become its priorities; the others are shown under them."""


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
    cluster: str | None = None
    """An evidence column whose value groups events that are one decision (a flash blinding two
    teammates): the chance test counts them once, or it would see a signal in every such flash."""

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
    watched = REGISTRY[rule.metric]
    if not rule.history and not (
        (watched.unit == "pct" and watched.cases and not watched.signed)
        or (watched.unit == "count" and not watched.cases)
    ):
        raise ValueError(f"rule {rule.id!r} watches {rule.metric!r}: no chance test for it")
    if not rule.history and watched.unit == "count" and watched.better != "lower":
        raise ValueError(f"rule {rule.id!r}: a total is only tested for having too many events")
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
    chance: float | None = None
    """How likely so many events are at the reference's rate. None when it was not tested: a
    pattern rule, a reference with no such events, a reference of medians."""
    strong: bool = False
    """A clear signal: `chance` is below `advice.strong_chance`."""

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


def _binomial_tail(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    if k > n or p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    return min(
        1.0,
        sum(
            exp(
                lgamma(n + 1)
                - lgamma(i + 1)
                - lgamma(n - i + 1)
                + i * log(p)
                + (n - i) * log(1.0 - p)
            )
            for i in range(k, n + 1)
        ),
    )


def _poisson_tail(k: int, mean: float) -> float:
    """P(X >= k) for X ~ Poisson(mean)."""
    if k <= 0:
        return 1.0
    if mean <= 0.0:
        return 0.0
    below = sum(exp(i * log(mean) - mean - lgamma(i + 1)) for i in range(k))
    return max(0.0, 1.0 - below)


def _rounds(ds: Dataset, player: int) -> float:
    return float(ds.rounds_played().filter(pl.col("steamid") == player)["rounds"].sum())


def _cases(rule: Rule, ds: Dataset, player: int, params: Mapping[str, ParamValue] | None) -> int:
    """What the watched metric is computed over, for the player: its count metrics, or rounds."""
    cases = REGISTRY[rule.metric].cases
    total = _rounds(ds, player) if ROUNDS in cases else 0.0
    counts = [c for c in cases if c != ROUNDS]
    if counts:
        known = rule.evidence_params(params)
        values = compute(ds, counts, params=known).filter(pl.col("steamid") == player)
        total += float(values["value"].fill_null(0.0).sum())
    return round(total)


def chance(
    rule: Rule,
    ds: Dataset,
    player: int,
    evidence: pl.DataFrame,
    *,
    basis: str,
    reference: float,
    params: Mapping[str, ParamValue] | None = None,
) -> float | None:
    """How likely at least this many events are at the reference's rate. A total is a Poisson
    count; a percentage, a binomial count of bad cases among the metric's cases. The reference is
    taken as exact: its own noise is left out, and `docs/calibration.md` measures the result.
    None for a reference with no such events: a 100 % over two clutches says nothing exact."""
    events = evidence.height
    distinct = events
    if rule.cluster is not None:
        # Grenade ids and the like are only unique within a match.
        groups = evidence.select("match_id", rule.cluster)
        distinct = groups.drop_nulls().n_unique() + groups[rule.cluster].null_count()
    shrink = distinct / events if events else 1.0
    metric = REGISTRY[rule.metric]
    if metric.cases:
        bad = reference / 100 if metric.better == "lower" else 1.0 - reference / 100
        if bad <= 0.0:
            return None
        cases = max(_cases(rule, ds, player, params), events)
        return _binomial_tail(distinct, round(cases * shrink), bad)
    mean = reference * _rounds(ds, player) if basis == "per_round" else reference
    if mean <= 0.0:
        return None
    return _poisson_tail(distinct, mean * shrink)


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
    odds: float | None = None,
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
        chance=odds,
        strong=odds is not None and odds < float(rule.param("advice.strong_chance")),
    )


def _events(finding: Finding) -> set[tuple[Any, ...]]:
    return set(finding.evidence.select("match_id", "round", "tick").iter_rows())


def split_findings(
    findings: Iterable[Finding], limit: int = PRIORITIES, overlap: float = 0.5
) -> tuple[list[Finding], list[Finding]]:
    """The priorities and the other findings, clear signals first, then costliest first.

    The priorities are the first `limit` findings in that order. Two findings whose events mostly
    repeat each other (more than `overlap` of the smaller one) are not both priorities: two rules
    on the same deaths make one priority, not two. Events, not rounds: a finding spread over half
    the session's rounds would otherwise hide every other one. Whatever is not a priority is among
    the others, including findings skipped for their overlap."""
    kept: list[Finding] = []
    others: list[Finding] = []
    for candidate in sorted(findings, key=lambda f: (not f.strong, -f.cost, -f.events, f.rule)):
        events = _events(candidate)
        if len(kept) >= limit or any(
            len(events & _events(k)) > overlap * min(len(events), len(_events(k))) for k in kept
        ):
            others.append(candidate)
        else:
            kept.append(candidate)
    return kept, others


def prioritize(
    findings: Iterable[Finding], limit: int = PRIORITIES, overlap: float = 0.5
) -> list[Finding]:
    """The priorities alone (`split_findings`)."""
    return split_findings(findings, limit, overlap)[0]
