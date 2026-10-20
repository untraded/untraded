# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
from __future__ import annotations

import dataclasses
from pathlib import Path

import polars as pl
import pytest

from untraded import fixtures
from untraded.advice import RULES, Rule, find, prioritize
from untraded.advice.engine import EVIDENCE_COLUMNS, Finding, rule, worse
from untraded.derive import derive
from untraded.metrics import REGISTRY, Dataset, compute
from untraded.metrics.dataset import MatchTables

FIXTURES = Path(__file__).parent / "fixtures"
NAMES = ["premier-half", "premier-abandon", "faceit-bots"]


def tables(name: str, match_id: str | None = None) -> MatchTables:
    canonical = fixtures.read(FIXTURES / name)
    if match_id is not None:
        canonical["match"] = canonical["match"].with_columns(pl.lit(match_id).alias("match_id"))
    return {**canonical, **derive(canonical).tables()}


@pytest.fixture(scope="module", params=NAMES)
def dataset(request: pytest.FixtureRequest) -> Dataset:
    return Dataset.from_matches([tables(request.param)])


def evidence(ds: Dataset, rule_id: str, player: int) -> pl.DataFrame:
    rule = RULES[rule_id]
    return rule.evidence(ds, player, rule.evidence_params())


def value(values: pl.DataFrame, metric: str, player: int) -> float:
    """The metric's value, 0 when undefined (a rate without events)."""
    row = values.filter((pl.col("metric") == metric) & (pl.col("steamid") == player))
    found = row["value"][0]
    return 0.0 if found is None else float(found)


# The evidence is what the metric counts ---------------------------------------------------


def test_evidence_matches_the_watched_metrics(dataset: Dataset) -> None:
    values = compute(dataset)
    for player in dataset.players()["steamid"].to_list():
        attempts = sum(value(values, f"clutch.attempts_1v{n}", player) for n in range(1, 6))
        wins = sum(value(values, f"clutch.wins_1v{n}", player) for n in range(1, 6))
        opening_kills = value(values, "duel.opening_kills", player)
        conversion = value(values, "duel.opening_win_conversion_pct", player)
        expected = {
            "trade.untraded_deaths": value(values, "trade.untraded_deaths", player),
            "trade.isolated_deaths": value(values, "duel.isolated_deaths", player),
            "duel.opening_deaths": value(values, "duel.opening_deaths", player),
            "util.team_flashes": value(values, "util.teammates_flashed", player),
            "clutch.clutches_lost": attempts - wins,
            "duel.openings_lost": round(opening_kills * (1 - conversion / 100))
            if opening_kills
            else 0,
        }
        for rule_id, count in expected.items():
            assert evidence(dataset, rule_id, player).height == count, (rule_id, player)


def test_wasted_utility_adds_up_to_the_metric(dataset: Dataset) -> None:
    values = compute(dataset)
    for player in dataset.players()["steamid"].to_list():
        deaths = value(values, "base.deaths", player)
        if not deaths:
            continue
        wasted = float(evidence(dataset, "util.wasted_utility", player)["value"].sum())
        assert wasted / deaths == pytest.approx(value(values, "util.unused_value_at_death", player))


def test_missed_trades_are_unconverted_opportunities(dataset: Dataset) -> None:
    values = compute(dataset)
    for player in dataset.players()["steamid"].to_list():
        missed = evidence(dataset, "trade.missed_trades", player).height
        chances = value(values, "trade.kill_opportunities", player)
        assert missed <= chances
        # One trade kill can avenge two teammates killed by the same enemy, so conversions are
        # not bounded by trade kills; without any trade kill, every opportunity is missed.
        if value(values, "trade.trade_kills", player) == 0:
            assert missed == chances


def test_evidence_rows_are_the_players_rounds(dataset: Dataset) -> None:
    for player in dataset.players()["steamid"].to_list():
        mine = dataset.played.filter(pl.col("steamid") == player).select("match_id", "round")
        for rule_id in RULES:
            rows = evidence(dataset, rule_id, player)
            assert tuple(rows.columns[:5]) == EVIDENCE_COLUMNS
            assert (
                rows.select("match_id", "round")
                .join(mine, on=["match_id", "round"], how="anti")
                .is_empty()
            )


# Triggers ------------------------------------------------------------------------------------


def comparison(ds: Dataset, player: int, factor: float) -> pl.DataFrame:
    """The session's own values as the comparison, with a reference `factor` times better."""
    values = compute(ds).filter(pl.col("steamid") == player)
    better = pl.col("metric").replace_strict(
        {m.id: m.better for m in REGISTRY.values()}, default="neutral"
    )
    return values.select(
        "metric",
        pl.lit("value").alias("basis"),
        pl.col("value").alias("session"),
        pl.when(better == "higher")
        .then(pl.col("value") * factor)
        .when(better == "lower")
        .then(pl.col("value") / factor)
        .otherwise(pl.col("value"))
        .alias("reference"),
    )


def test_worse_respects_the_direction_and_the_gap() -> None:
    deaths, kast = RULES["trade.untraded_deaths"], RULES["duel.opening_deaths"]
    assert worse(deaths, 1.2, 1.0)  # 20 % more untraded deaths
    assert not worse(deaths, 1.1, 1.0)  # 10 %: under the 15 % gap
    assert not worse(deaths, 0.5, 1.0)  # better
    assert worse(kast, 40.0, 50.0)
    assert not worse(kast, 60.0, 50.0)
    assert not worse(kast, None, 50.0)


def test_rules_fire_only_against_a_clearly_better_reference() -> None:
    ds = Dataset.from_matches([tables("premier-abandon")])
    player = max(
        ds.players()["steamid"].to_list(),
        key=lambda p: evidence(ds, "trade.untraded_deaths", p).height,
    )
    fired = {f.rule for f in find(ds, player, comparison(ds, player, 2.0))}
    assert "trade.untraded_deaths" in fired
    assert find(ds, player, comparison(ds, player, 1.0)) == []  # same as the reference


def test_too_few_events_do_not_make_a_finding() -> None:
    ds = Dataset.from_matches([tables("premier-half")])
    player = ds.players()["steamid"][0]
    strict = dataclasses.replace(RULES["trade.untraded_deaths"], params={"advice.min_events": 99})
    assert find(ds, player, comparison(ds, player, 2.0), rules=[strict]) == []


def test_a_rule_cannot_watch_a_neutral_metric() -> None:
    with pytest.raises(ValueError, match="neutral"):
        rule(
            Rule(
                id="test.neutral",
                version="1.0.0",
                family="duel",
                metric="duel.opening_attempts",
                evidence=RULES["duel.opening_deaths"].evidence,
                actions=(),
            )
        )


# Cost and priorities ---------------------------------------------------------------------------


def test_cost_counts_rounds_and_weighs_the_lost_ones() -> None:
    ds = Dataset.from_matches([tables("premier-abandon")])
    for player in ds.players()["steamid"].to_list():
        for found in find(ds, player, comparison(ds, player, 3.0)):
            assert 0 <= found.rounds_lost <= found.rounds_touched <= found.events
            assert found.cost == pytest.approx(
                found.rounds_lost + 0.25 * (found.rounds_touched - found.rounds_lost)
            )
            assert found.message_key == f"advice.{found.rule}"
            assert found.actions


def fake(rule_id: str, cost: float, rounds: list[int]) -> Finding:
    rows = pl.DataFrame({"match_id": ["m"] * len(rounds), "round": rounds})
    return Finding(
        rule=rule_id,
        rule_version="1.0.0",
        metric="m",
        metric_version="1.0.0",
        basis="value",
        session=None,
        reference=None,
        evidence=rows,
        rounds_touched=len(rounds),
        rounds_lost=0,
        cost=cost,
        message_key="k",
        actions=(),
        indicator="m",
    )


def test_priorities_are_the_costliest_without_repeating_rounds() -> None:
    findings = [
        fake("a", 5, [1, 2, 3, 4]),
        fake("b", 4, [1, 2, 3, 9]),  # 3 of its 4 rounds are already a's
        fake("c", 3, [10, 11]),
        fake("d", 2, [12]),
        fake("e", 1, [13]),
    ]
    assert [f.rule for f in prioritize(findings)] == ["a", "c", "d"]
    assert [f.rule for f in prioritize(findings, limit=5)] == ["a", "c", "d", "e"]


# Pattern rule: a recurring death spot over the session and the days before it -------------------


def test_recurring_spot_looks_at_history_and_shows_the_session_deaths() -> None:
    days = [tables("premier-abandon", f"{i:064x}") for i in range(6)]
    session = Dataset.from_matches(days[-1:])
    history = Dataset.from_matches(days)
    spot = RULES["pos.recurring_death_spot"]
    loose = {"pos.recurring_min_rounds": 1, "pos.recurring_death_share": 0.2}
    for player in session.players()["steamid"].to_list():
        found = find(session, player, pl.DataFrame(), history=history, params=loose, rules=[spot])
        if not found:
            continue
        (finding,) = found
        assert set(finding.evidence["match_id"]) == {f"{5:064x}"}
        assert finding.details["history_events"] == 6 * finding.events
        assert {"map", "side", "zone"} <= set(finding.details)
        return
    pytest.fail("no recurring spot in six copies of the same match")


def test_rules_are_registered_with_valid_metrics() -> None:
    assert len(RULES) == 10
    for registered in RULES.values():
        assert registered.metric in REGISTRY
        assert registered.actions
        assert registered.version.count(".") == 2
