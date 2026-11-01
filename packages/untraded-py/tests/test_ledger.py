# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The ledger: every change of the round's win probability, credited so that each round adds up."""

from __future__ import annotations

import itertools
from pathlib import Path

import polars as pl
import pytest

from untraded import fixtures
from untraded.derive import derive
from untraded.winprob import default_model
from untraded.winprob.ledger import (
    PARTS,
    SCHEMA,
    Shares,
    _events,
    _rounds,
    _views,
    ledger,
    per_player,
)

FIXTURES = Path(__file__).parent / "fixtures"
NAMES = ("premier-half", "premier-abandon", "faceit-bots")


@pytest.fixture(scope="module", params=NAMES)
def tables(request: pytest.FixtureRequest) -> dict[str, pl.DataFrame]:
    return fixtures.read(FIXTURES / request.param)


@pytest.fixture(scope="module")
def half() -> dict[str, pl.DataFrame]:
    return fixtures.read(FIXTURES / "premier-half")


def test_every_round_adds_up(tables: dict[str, pl.DataFrame]) -> None:
    credits = ledger(tables, default_model())
    assert credits.schema == pl.Schema(SCHEMA)
    assert not credits.is_empty()
    assert credits["credit"].is_finite().all()
    assert set(credits["part"].unique().to_list()) <= set(PARTS)
    # The ten players' credits cancel out, round by round.
    totals = credits.group_by("round").agg(pl.col("credit").sum())
    assert totals.select(pl.col("credit").abs().max()).item() < 1e-9
    # Every regular round has a ledger.
    rounds = _rounds(tables)
    assert set(credits["round"].unique().to_list()) == set(rounds["round"].to_list())
    # A side's credits add up to its result minus its chance at the start (the start view).
    events = _events(tables, rounds)
    features, _ = _views(tables, rounds, events)
    p0 = dict(
        zip(
            features["view"].to_list(),
            default_model().predict(features).tolist(),
            strict=True,
        )
    )
    starts = events.filter(pl.col("kind") == "start").select("round", "seq").rows()
    winners = dict(tables["round"].select("round", "winner_side").iter_rows())
    for number, seq in starts:
        ct = credits.filter(pl.col("round") == number, pl.col("side") == "CT")["credit"].sum()
        result = 1.0 if winners[number] == "CT" else 0.0
        assert ct == pytest.approx(result - p0[seq * 2], abs=1e-9)


def test_the_last_kill_of_an_elimination_is_a_kill(tables: dict[str, pl.DataFrame]) -> None:
    credits = ledger(tables, default_model())
    eliminated = _rounds(tables).filter(pl.col("reason").cast(pl.String) == "elimination")
    checked = 0
    for number, over in eliminated.select("round", "over").rows():
        # The kill that ends the round (kills after it are exit frags, not credited).
        last = (
            tables["kill"]
            .filter(pl.col("round") == number, pl.col("tick") <= over)
            .sort("tick")
            .tail(1)
        )
        if last.is_empty() or last["victim"][0] is None:
            continue
        rows = credits.filter(
            pl.col("round") == number,
            pl.col("event") == "kill",
            pl.col("tick") == last["tick"][0],
        )
        # Credited as a kill, the victim debited; nothing is left for the round's end.
        assert rows.filter(pl.col("steamid") == last["victim"][0])["credit"].sum() < 0
        end = credits.filter(pl.col("round") == number, pl.col("event") == "end")
        assert end.select(pl.col("credit").abs().sum()).item() < 1e-9
        checked += 1
    if not eliminated.is_empty():
        assert checked > 0


def test_a_lone_planter_or_defuser_takes_it_all(tables: dict[str, pl.DataFrame]) -> None:
    credits = ledger(tables, default_model())
    rounds = _rounds(tables)
    events = _events(tables, rounds)
    _, players = _views(tables, rounds, events)
    for kind, side in (("plant", "T"), ("defuse", "CT")):
        for e in events.filter(pl.col("kind") == kind).iter_rows(named=True):
            living = players.filter(
                pl.col("view") == e["seq"] * 2, pl.col("side") == side, pl.col("is_alive")
            )["steamid"].to_list()
            rows = credits.filter(
                pl.col("round") == e["round"],
                pl.col("event") == kind,
                pl.col("side") == side,
            )
            # Only the living share it: no dead teammate is credited.
            assert set(rows["steamid"].to_list()) <= set(living) | {e["actor"]}


def test_nothing_after_the_round_is_decided(half: dict[str, pl.DataFrame]) -> None:
    credits = ledger(half, default_model())
    events = credits.filter(pl.col("event") != "end")
    for (_,), rows in events.group_by(["round"]):
        ordered = rows.sort("tick")
        decided = ordered.filter(pl.col("p_ct_after").is_in([0.0, 1.0]))
        if decided.is_empty():
            continue
        at = decided["tick"].min()
        assert ordered.filter(pl.col("tick") > at).is_empty()


def test_a_kill_is_shared_and_the_victim_debited(half: dict[str, pl.DataFrame]) -> None:
    credits = ledger(half, default_model())
    kills = credits.filter(pl.col("event") == "kill")
    for row in (
        half["kill"]
        .filter(pl.col("attacker").is_not_null(), pl.col("victim").is_not_null())
        .filter(~pl.col("is_team_kill"))
        .head(10)
        .iter_rows(named=True)
    ):
        rows = kills.filter(pl.col("round") == row["round"], pl.col("tick") == row["tick"])
        if rows.is_empty():  # after the round was decided
            continue
        victim = rows.filter(pl.col("steamid") == row["victim"], pl.col("part") == "taken")
        others = rows.filter(pl.col("side") != row["victim_side"])
        assert victim["credit"].sum() == pytest.approx(-others["credit"].sum(), abs=1e-12)
        killer = float(others.filter(pl.col("steamid") == row["attacker"])["credit"].sum())
        gain = float(others["credit"].sum())
        # The killer has at least the final blow's share of what is shared.
        shares = Shares()
        most = shares.final + shares.damage + shares.flash + shares.trade
        assert abs(killer) >= abs(gain) * shares.final / most - 1e-12


def test_the_parts_add_up_to_the_swing(half: dict[str, pl.DataFrame]) -> None:
    credits = ledger(half, default_model())
    played = derive(half).tables()["round_player"].select("steamid", "round")
    table = per_player(credits, played)
    assert table.columns == ["steamid", "rounds", "swing", *PARTS]
    for row in table.iter_rows(named=True):
        assert row["swing"] == pytest.approx(sum(row[p] for p in PARTS))
    # Over the match, the players' credits cancel out.
    total = table.select((pl.col("swing") * pl.col("rounds")).sum()).item()
    assert total == pytest.approx(0, abs=1e-6)


def test_a_state_between_samples_has_the_earlier_events(half: dict[str, pl.DataFrame]) -> None:
    rounds = _rounds(half)
    events = _events(half, rounds)
    features, _ = _views(half, rounds, events)
    by_view = {row["view"]: row for row in features.iter_rows(named=True)}
    sampled: dict[int, list[int]] = {}
    for number, tick in half["player_tick"].select("round", "tick").unique().rows():
        sampled.setdefault(number, []).append(tick)

    def sample(number: int, tick: int) -> int:
        return max((t for t in sampled[number] if t < tick), default=-1)

    changes = events.filter(pl.col("kind").is_in(["damage", "kill"])).sort("seq").to_dicts()
    checked = 0
    for first, second in itertools.pairwise(changes):
        same = first["round"] == second["round"] and sample(
            first["round"], first["tick"]
        ) == sample(second["round"], second["tick"])
        a, b = by_view.get(first["seq"] * 2 + 1), by_view.get(second["seq"] * 2)
        if not same or a is None or b is None:
            continue
        # Both read the same sample: the second starts where the first left off.
        for name in ("alive_ct", "alive_t", "hp_ct", "hp_t", "armor_ct", "armor_t"):
            assert b[name] == pytest.approx(a[name]), name
        checked += 1
    assert checked > 0


def test_shares_are_checked() -> None:
    with pytest.raises(ValueError, match="killer"):
        Shares(final=0.0)
    with pytest.raises(ValueError, match="plant"):
        Shares(plant=1.5)
    half = fixtures.read(FIXTURES / "premier-half")
    with_flash = ledger(half, default_model())
    without = ledger(half, default_model(), Shares(flash=0))
    # Without the flash share, a kill's utility credit only goes to grenade damage on the victim.
    grenades = half["damage"].filter(pl.col("weapon").is_in(["hegrenade", "inferno", "molotov"]))
    hurt = set(grenades.select("round", "attacker").rows())
    killers = set(half["kill"].select("round", "attacker").rows())
    utility = without.filter(pl.col("event") == "kill", pl.col("part") == "utility")
    for number, steamid in utility.select("round", "steamid").rows():
        assert (number, steamid) in hurt | killers
    flashed = with_flash.filter(pl.col("event") == "kill", pl.col("part") == "utility")
    assert flashed.height > utility.height  # the flashers had a share
