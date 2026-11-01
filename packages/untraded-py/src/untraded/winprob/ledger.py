# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The ledger: every change of a round's win probability, credited to players.

The model gives the counter-terrorists' chance at the start of the round (P0), just before and
just after each event, and at the end. Each change goes to someone, so the credits of a round add
up exactly: the counter-terrorists' to `result - P0`, the terrorists' to the opposite, the ten
players' to zero. Over a match, the average player's credit is therefore zero by construction.

What moves the probability, and who it goes to (`Shares` holds the numbers):

- **damage** that does not kill: to the attacker; debited to the player hurt;
- **a kill**: debited to the victim. The killer's side shares it: `final` to the killer,
  `damage` to everyone who hurt the victim this round (by damage dealt), `flash` to the enemies
  who flashed the victim (blind at least `flash_min` more seconds at the kill, by that time), and
  `trade` to the teammate the victim had killed within `trade_window` seconds. A share with no
  one to take it is spread over the others;
- **the plant**: `plant` to the planter, the rest to the other living terrorists; debited to the
  living counter-terrorists;
- **the defuse**: `defuse` to the defuser, the rest to the other living counter-terrorists;
  debited to the living terrorists;
- **the time between events** ("hold": the clock, movement, pickups) and **the end of the round**
  (time running out, the explosion): to the living players of the side that gains, debited to the
  living players of the other;
- team damage and team kills are debited to their author; damage from the world or a suicide to
  the victim. The other side's gain goes to its living players.

Each credit is labelled with a `part` (`PARTS`): shooting, utility (grenades and flashes), trade,
objective, hold, taken (damage and deaths suffered) and team (harm to one's own side). The parts
of a player add up to their credit.

A state is the last `player_tick` sample before the event, with the effects of the events between
that sample and the event applied (a kill marks the victim dead, damage sets their health and
armor), so two events a tick apart do not share a state. Once an event decides the round (the
last enemy dies, the defuse), the round's ledger stops: later kills move nothing.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl

from untraded.winprob.features import _finish, _per_side
from untraded.winprob.model import Model

PARTS = ("shooting", "utility", "trade", "objective", "hold", "taken", "team")

UTILITY_WEAPONS = frozenset(
    {"hegrenade", "inferno", "molotov", "incgrenade", "smokegrenade", "flashbang", "decoy"}
)
"""Damage from these is `utility`; from any other weapon, `shooting`."""

VALID_REASONS = ("bomb_exploded", "bomb_defused", "elimination", "time_ran_out")
BALANCE = 1e-9
"""How far from zero a round's credits may add up (rounding)."""
MAX_EVENTS = 2000
"""Events a round may have for a ledger (a real round has a few hundred at most)."""

SCHEMA = {
    "round": pl.Int16,
    "tick": pl.Int32,
    "event": pl.String,
    "steamid": pl.UInt64,
    "side": pl.String,
    "part": pl.String,
    "credit": pl.Float64,
    "p_ct_before": pl.Float64,
    "p_ct_after": pl.Float64,
}

_ORDER = {"start": 0, "damage": 1, "kill": 2, "plant": 3, "defuse": 4, "end": 5}


@dataclass(frozen=True)
class Shares:
    """How a kill, a plant and a defuse are shared (the rest of the ledger has no parameter).
    The defaults are a starting point, near Leetify's published split; the published values are
    chosen on the corpus."""

    final: float = 0.35
    damage: float = 0.30
    flash: float = 0.15
    trade: float = 0.20
    plant: float = 0.5
    defuse: float = 0.7
    trade_window: float = 5.0
    """Seconds: the victim had killed a teammate of the killer this recently."""
    flash_min: float = 1.1
    """Seconds of blindness left at the kill for a flash to count."""

    def __post_init__(self) -> None:
        kill = (self.final, self.damage, self.flash, self.trade)
        if any(s < 0 for s in kill) or sum(kill) <= 0 or self.final <= 0:
            raise ValueError("kill shares must be non-negative, the killer's positive")
        if not (0 <= self.plant <= 1 and 0 <= self.defuse <= 1):
            raise ValueError("plant and defuse shares must be within 0 and 1")


DEFAULT_SHARES = Shares()


def _rounds(tables: Mapping[str, pl.DataFrame]) -> pl.DataFrame:
    """The rounds with a ledger: a winner and a regular ending."""
    return (
        tables["round"]
        .filter(
            pl.col("winner_side").is_not_null(),
            pl.col("freeze_end_tick").is_not_null(),
            pl.col("reason").cast(pl.String).is_in(VALID_REASONS),
        )
        .unique("round", keep="none")  # a malformed table repeating a round: no ledger for it
        .with_columns(
            pl.min_horizontal("end_tick", "bomb_defused_tick", "bomb_exploded_tick").alias("over")
        )
    )


def _events(tables: Mapping[str, pl.DataFrame], rounds: pl.DataFrame) -> pl.DataFrame:
    """Every event of the ledger, in order (`seq`): the start and end of each round, damage that
    does not kill, kills, plants and defuses."""
    cols = {
        "round": pl.Int16,
        "tick": pl.Int32,
        "kind": pl.String,
        "actor": pl.UInt64,
        "victim": pl.UInt64,
        "weapon": pl.String,
        "health_after": pl.Int16,
        "armor_after": pl.Int16,
    }
    timing = rounds.select(
        "round",
        "freeze_end_tick",
        "over",
        (pl.col("reason").cast(pl.String) == "elimination").alias("eliminated"),
    )
    # The round's last kill shares the round's last tick when it ends by elimination: it counts.
    in_play = (pl.col("tick") > pl.col("freeze_end_tick")) & (
        (pl.col("tick") < pl.col("over"))
        | ((pl.col("tick") == pl.col("over")) & pl.col("eliminated"))
    )

    def frame(df: pl.DataFrame, **exprs: pl.Expr) -> pl.DataFrame:
        return df.select(
            *(exprs.get(name, pl.lit(None)).cast(dtype).alias(name) for name, dtype in cols.items())
        )

    damage = (
        tables["damage"]
        .join(timing, on="round")
        .filter(pl.col("victim").is_not_null(), pl.col("health_after") > 0, in_play)
    )
    kills = tables["kill"].join(timing, on="round").filter(pl.col("victim").is_not_null(), in_play)
    plants = rounds.filter(
        pl.col("bomb_planted_tick").is_not_null(), pl.col("bomb_planted_tick") < pl.col("over")
    )
    defuses = rounds.filter(pl.col("bomb_defused_tick").is_not_null())
    parts = [
        frame(
            rounds, round=pl.col("round"), tick=pl.col("freeze_end_tick") + 1, kind=pl.lit("start")
        ),
        frame(
            damage,
            round=pl.col("round"),
            tick=pl.col("tick"),
            kind=pl.lit("damage"),
            actor=pl.col("attacker"),
            victim=pl.col("victim"),
            weapon=pl.col("weapon"),
            health_after=pl.col("health_after"),
            armor_after=pl.col("armor_after"),
        ),
        frame(
            kills,
            round=pl.col("round"),
            tick=pl.col("tick"),
            kind=pl.lit("kill"),
            actor=pl.col("attacker"),
            victim=pl.col("victim"),
            weapon=pl.col("weapon"),
        ),
        frame(
            plants,
            round=pl.col("round"),
            tick=pl.col("bomb_planted_tick"),
            kind=pl.lit("plant"),
            actor=pl.col("bomb_planter"),
        ),
        frame(
            defuses,
            round=pl.col("round"),
            tick=pl.col("bomb_defused_tick"),
            kind=pl.lit("defuse"),
            actor=pl.col("bomb_defuser"),
        ),
        frame(rounds, round=pl.col("round"), tick=pl.col("over"), kind=pl.lit("end")),
    ]
    events = pl.concat(parts).with_row_index("source")
    # A crafted demo could pile up events in a round: such a round gets no ledger.
    events = events.filter(pl.len().over("round") <= MAX_EVENTS)
    return (
        events.with_columns(pl.col("kind").replace_strict(_ORDER).alias("order"))
        .sort("round", "tick", "order", "source")
        .with_row_index("seq")
        .drop("source", "order")
    )


def _views(
    tables: Mapping[str, pl.DataFrame], rounds: pl.DataFrame, events: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """The states the ledger needs, one per view (`view` = 2 * seq before the event, + 1 after):
    the model's features (with `map`), and the players of each view (`view`, `steamid`, `side`,
    `alive`). Events without a `player_tick` sample before them are dropped."""
    ticks = tables["player_tick"]
    samples = ticks.select("round", "tick").unique().sort("tick")
    snapped = (
        events.sort("tick")
        .join_asof(
            samples.rename({"tick": "snap"}),
            left_on="tick",
            right_on="snap",
            by="round",
            strategy="backward",
            allow_exact_matches=False,
            check_sortedness=False,
        )
        .filter(pl.col("snap").is_not_null())
        .sort("seq")
    )
    mutating = snapped.filter(pl.col("kind").is_in(["damage", "kill"])).select(
        "round",
        pl.col("seq").alias("j"),
        pl.col("tick").alias("j_tick"),
        pl.col("kind").alias("j_kind"),
        pl.col("victim").alias("steamid"),
        "health_after",
        "armor_after",
    )
    # Before an event: the events after its sample and before it in order; after: itself too.
    # In order, they run from the first one after the sample up to the event, so only that range
    # is joined (not every pair of the round).
    firsts = (
        snapped.select("round", "seq", "snap")
        .sort("snap")
        .join_asof(
            mutating.sort("j_tick", "j").select("round", "j_tick", pl.col("j").alias("first")),
            left_on="snap",
            right_on="j_tick",
            by="round",
            strategy="forward",
            allow_exact_matches=False,
            check_sortedness=False,
        )
        .filter(pl.col("first").is_not_null(), pl.col("first") < pl.col("seq"))
    )
    columns = ["round", "seq", "snap", "j", "j_tick", "j_kind", "steamid"]
    columns += ["health_after", "armor_after"]
    before = (
        firsts.with_columns(pl.int_ranges("first", "seq", dtype=pl.UInt32).alias("j"))
        .explode("j")
        .select("round", "seq", "snap", "j")
        .join(mutating, on=["round", "j"])
        .select(columns)
    )
    itself = (
        snapped.select("round", "seq", "snap", pl.col("seq").alias("j"))
        .join(mutating, on=["round", "j"])
        .select(columns)
    )
    after = pl.concat([before, itself])
    mods = (
        pl.concat(
            [
                before.with_columns((pl.col("seq") * 2).alias("view")),
                after.with_columns((pl.col("seq") * 2 + 1).alias("view")),
            ]
        )
        .sort("view", "j")
        .group_by("view", "steamid")
        .agg(
            (pl.col("j_kind") == "kill").any().alias("killed"),
            pl.col("health_after").filter(pl.col("j_kind") == "damage").last().alias("hp_mod"),
            pl.col("armor_after").filter(pl.col("j_kind") == "damage").last().alias("armor_mod"),
        )
    )
    views = pl.concat(
        [
            snapped.with_columns((pl.col("seq") * 2).alias("view"), pl.lit(False).alias("after")),
            snapped.filter(~pl.col("kind").is_in(["start", "end"])).with_columns(
                (pl.col("seq") * 2 + 1).alias("view"), pl.lit(True).alias("after")
            ),
        ]
    ).join(rounds.select("round", "freeze_end_tick", "bomb_planted_tick"), on="round")
    views = views.with_columns(
        (pl.col("tick") - 1).alias("at"),
        # The plant's after view: the bomb is down at the view's own tick.
        pl.when(pl.col("after") & (pl.col("kind") == "plant"))
        .then(pl.col("tick") - 1)
        .when(pl.col("bomb_planted_tick") >= pl.col("tick"))
        .then(None)
        .otherwise(pl.col("bomb_planted_tick"))
        .alias("bomb_planted_tick"),
    )
    rows = (
        views.select("view", "round", "snap")
        .join(ticks, left_on=["round", "snap"], right_on=["round", "tick"])
        .with_columns(pl.col("snap").alias("tick"))
        .join(mods, on=["view", "steamid"], how="left")
        .with_columns(
            (pl.col("is_alive") & ~pl.col("killed").fill_null(False)).alias("is_alive"),
            pl.coalesce(pl.col("hp_mod").cast(pl.Int16), pl.col("health")).alias("health"),
            pl.coalesce(pl.col("armor_mod").cast(pl.Int16), pl.col("armor")).alias("armor"),
        )
    )
    sides = _per_side(rows, tables, keys=("view", "round"))
    match = tables["match"].row(0, named=True)
    timing = views.select(
        "view", "round", "freeze_end_tick", "bomb_planted_tick", pl.col("at").alias("tick")
    )
    features = _finish(sides.join(timing, on=["view", "round"]), float(match["tickrate"]))
    features = features.with_columns(pl.lit(match["map"]).alias("map"))
    players = rows.filter(pl.col("steamid").is_not_null()).select(
        "view", "steamid", pl.col("side").cast(pl.String), "is_alive"
    )
    return features, players


def _decided(row: Mapping[str, Any]) -> float | None:
    if row["alive_ct"] <= 0:
        return 0.0
    if row["alive_t"] <= 0 and row["planted"] <= 0:
        return 1.0
    return None


class _Book:
    """Credits of one match, as rows of `SCHEMA`."""

    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []

    def add(
        self,
        event: Mapping[str, Any],
        p: tuple[float, float],
        credits: Mapping[tuple[int, str, str], float],
    ) -> None:
        for (steamid, side, part), credit in credits.items():
            if credit == 0:
                continue
            self.rows.append(
                {
                    "round": event["round"],
                    "tick": event["tick"],
                    "event": event["kind"],
                    "steamid": steamid,
                    "side": side,
                    "part": part,
                    "credit": credit,
                    "p_ct_before": p[0],
                    "p_ct_after": p[1],
                }
            )


def _spread(
    out: dict[tuple[int, str, str], float],
    amount: float,
    weights: Mapping[int, float],
    side: str,
    part: str,
) -> None:
    total = sum(weights.values())
    if not math.isfinite(total) or total <= 0:
        return  # nothing credited: the round no longer adds up, and `ledger` drops it
    for steamid, w in weights.items():
        out[(steamid, side, part)] += amount * w / total


def ledger(
    tables: Mapping[str, pl.DataFrame], model: Model, shares: Shares = DEFAULT_SHARES
) -> pl.DataFrame:
    """Every credit of a match (columns `SCHEMA`). `credit` is seen by the player's side, in
    probability (1 = a whole round); `p_ct_before` and `p_ct_after` frame the change it shares."""
    return credit(prepare(tables, model), shares)


@dataclass(frozen=True)
class Prepared:
    """A match's probabilities and who was where, ready to be credited: `prepare` runs the model
    once, `credit` shares the changes (cheap, so many `Shares` can be tried on one match)."""

    tickrate: float
    prob: Mapping[int, float]
    alive: Mapping[int, Mapping[str, list[int]]]
    side_of: Mapping[int, Mapping[int, str]]
    dealt: Mapping[tuple[int, int], list[tuple[int, int, str, int]]]
    blinds: Mapping[tuple[int, int], list[tuple[int, int, float]]]
    kills_by: Mapping[tuple[int, int], list[tuple[int, int]]]
    flash_assist: Mapping[tuple[int, int, int], int]
    chains: list[tuple[int, bool, list[dict[str, Any]]]]
    """Each round with a ledger: its number, whether the counter-terrorists won, its events."""


def prepare(tables: Mapping[str, pl.DataFrame], model: Model) -> Prepared:
    """The model's probabilities for every state of a match, and the lookups `credit` needs."""
    tickrate = float(tables["match"]["tickrate"][0] or 0)
    if not math.isfinite(tickrate) or tickrate <= 0:
        raise ValueError(f"the match's tickrate must be positive, not {tickrate}")
    rounds = _rounds(tables)
    events = _events(tables, rounds)
    if rounds.is_empty():
        return Prepared(tickrate, {}, {}, {}, {}, {}, {}, {}, [])
    features, players = _views(tables, rounds, events)
    p = model.predict(features)
    prob: dict[int, float] = {}
    for view, value, row in zip(
        features["view"].to_list(), p, features.iter_rows(named=True), strict=True
    ):
        decided = _decided(row)
        prob[view] = float(value) if decided is None else decided
    alive: dict[int, dict[str, list[int]]] = defaultdict(lambda: {"CT": [], "T": []})
    side_of: dict[int, dict[int, str]] = defaultdict(dict)
    for row in players.iter_rows(named=True):
        if row["side"] not in ("CT", "T"):
            continue
        side_of[row["view"]][row["steamid"]] = row["side"]
        if row["is_alive"]:
            alive[row["view"]][row["side"]].append(row["steamid"])

    damage = tables["damage"].filter(
        ~pl.col("is_team_damage"), pl.col("attacker").is_not_null(), pl.col("victim").is_not_null()
    )
    dealt: dict[tuple[int, int], list[tuple[int, int, str, int]]] = defaultdict(list)
    for d in damage.select("round", "victim", "tick", "attacker", "weapon", "dmg_health").rows():
        dealt[(d[0], d[1])].append((d[2], d[3], d[4] or "", d[5] or 0))
    blinds: dict[tuple[int, int], list[tuple[int, int, float]]] = defaultdict(list)
    for b in (
        tables["blind"]
        .filter(
            ~pl.col("is_teammate"),
            ~pl.col("is_self"),
            pl.col("flasher").is_not_null(),
            pl.col("duration").is_finite(),
        )
        .select("round", "victim", "tick", "flasher", "duration")
        .rows()
    ):
        blinds[(b[0], b[1])].append((b[2], b[3], float(b[4] or 0)))
    kills_by: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for k in (
        tables["kill"]
        .filter(pl.col("attacker").is_not_null(), pl.col("victim").is_not_null())
        .filter(~pl.col("is_team_kill"))
        .select("round", "attacker", "tick", "victim")
        .rows()
    ):
        kills_by[(k[0], k[1])].append((k[2], k[3]))
    flash_assist = {
        (k[0], k[1], k[2]): k[3]
        for k in tables["kill"]
        .filter(pl.col("flash_assist"), pl.col("assister").is_not_null())
        .select("round", "tick", "victim", "assister")
        .rows()
    }

    won = {r["round"]: r["winner_side"] == "CT" for r in rounds.iter_rows(named=True)}
    chains = []
    for (number,), chain in events.filter(
        (pl.col("seq") * 2).is_in(features["view"].implode())
    ).group_by(["round"], maintain_order=True):
        rows = chain.to_dicts()
        if rows[0]["kind"] != "start" or rows[-1]["kind"] != "end":
            continue  # no sample at the round's start or end: no ledger
        chains.append((int(number), won[number], rows))
    return Prepared(tickrate, prob, alive, side_of, dealt, blinds, kills_by, flash_assist, chains)


def credit(prepared: Prepared, shares: Shares = DEFAULT_SHARES) -> pl.DataFrame:
    """The credits of a prepared match under `shares` (columns `SCHEMA`)."""
    tickrate, prob, alive, side_of = (
        prepared.tickrate,
        prepared.prob,
        prepared.alive,
        prepared.side_of,
    )
    dealt, blinds = prepared.dealt, prepared.blinds
    kills_by, flash_assist = prepared.kills_by, prepared.flash_assist
    book = _Book()
    for _number, ct_won, rows in prepared.chains:
        start, end, inner = rows[0], rows[-1], rows[1:-1]
        result = 1.0 if ct_won else 0.0
        prev = prob[start["seq"] * 2]
        last_view = start["seq"] * 2
        decided = False
        for e in inner:
            vb, va = e["seq"] * 2, e["seq"] * 2 + 1
            if va not in prob:
                continue
            pb, pa = prob[vb], prob[va]
            if e["kind"] == "defuse":
                pa = 1.0
            book.add(e | {"kind": "hold"}, (prev, pb), _hold(pb - prev, alive, side_of, vb))
            book.add(
                e,
                (pb, pa),
                _event(
                    e,
                    pa - pb,
                    vb,
                    alive,
                    side_of,
                    shares,
                    tickrate,
                    dealt,
                    blinds,
                    kills_by,
                    flash_assist,
                ),
            )
            prev, last_view = pa, va
            if pa in (0.0, 1.0):
                decided = True
                break
        ve = end["seq"] * 2
        if not decided and ve in prob:
            pe = prob[ve]
            book.add(end | {"kind": "hold"}, (prev, pe), _hold(pe - prev, alive, side_of, ve))
            prev, last_view = pe, ve
        book.add(end, (prev, result), _hold(result - prev, alive, side_of, last_view, part="hold"))
    credits = pl.DataFrame(book.rows, schema=SCHEMA)
    # Every round adds up by construction; one that does not (a side with no player in a view)
    # is left out rather than published wrong.
    balanced = (
        credits.group_by("round")
        .agg(pl.col("credit").sum().abs().alias("off"))
        .filter(pl.col("off") < BALANCE)["round"]
    )
    return credits.filter(pl.col("round").is_in(balanced.implode()))


def _gain(side: str, d: float) -> float:
    """A change of the counter-terrorists' probability, seen by `side`."""
    return d if side == "CT" else -d


def _living(
    alive: Mapping[int, Mapping[str, list[int]]],
    side_of: Mapping[int, Mapping[int, str]],
    view: int,
    side: str,
    but: int | None = None,
) -> list[int]:
    """The living players of `side` in `view` (but one), or all of that side's players when no
    one else is alive: a side's change always has someone to take it."""
    living = [s for s in alive[view][side] if s != but]
    if living:
        return living
    everyone = [s for s, sd in side_of[view].items() if sd == side and s != but]
    return everyone or ([but] if but is not None else [])


def _hold(
    d: float,
    alive: Mapping[int, Mapping[str, list[int]]],
    side_of: Mapping[int, Mapping[int, str]],
    view: int,
    part: str = "hold",
) -> dict[tuple[int, str, str], float]:
    out: dict[tuple[int, str, str], float] = defaultdict(float)
    if d == 0:
        return out
    for side in ("CT", "T"):
        living = _living(alive, side_of, view, side)
        if living:
            _spread(out, _gain(side, d), dict.fromkeys(living, 1.0), side, part)
    return out


def _event(
    e: Mapping[str, Any],
    d: float,
    view: int,
    alive: Mapping[int, Mapping[str, list[int]]],
    side_of: Mapping[int, Mapping[int, str]],
    shares: Shares,
    tickrate: float,
    dealt: Mapping[tuple[int, int], list[tuple[int, int, str, int]]],
    blinds: Mapping[tuple[int, int], list[tuple[int, int, float]]],
    kills_by: Mapping[tuple[int, int], list[tuple[int, int]]],
    flash_assist: Mapping[tuple[int, int, int], int],
) -> dict[tuple[int, str, str], float]:
    out: dict[tuple[int, str, str], float] = defaultdict(float)
    if d == 0:
        return out
    kind, actor, victim = e["kind"], e["actor"], e["victim"]
    sides = side_of[view]
    if kind in ("plant", "defuse"):
        side = "T" if kind == "plant" else "CT"
        other = "CT" if side == "T" else "T"
        share = shares.plant if kind == "plant" else shares.defuse
        g = _gain(side, d)
        # Only living teammates help: a lone planter or defuser takes it all.
        helpers = [h for h in alive[view][side] if h != actor]
        if actor is None and not helpers:
            helpers = _living(alive, side_of, view, side)
        if actor is not None:
            out[(actor, side, "objective")] += g * (share if helpers else 1.0)
        if helpers:
            rest = g * (1 - share) if actor is not None else g
            _spread(out, rest, dict.fromkeys(helpers, 1.0), side, "objective")
        _spread(
            out,
            _gain(other, d),
            dict.fromkeys(_living(alive, side_of, view, other), 1.0),
            other,
            "objective",
        )
        return out
    v_side = sides.get(victim)
    if v_side is None:  # a victim the demo does not place: shared like the clock
        return _hold(d, alive, side_of, view)
    a_side = "CT" if v_side == "T" else "T"
    a_known = sides.get(actor) if actor is not None else None
    harm = _gain(v_side, d)
    gain = _gain(a_side, d)
    passive = dict.fromkeys(_living(alive, side_of, view, a_side), 1.0)
    if a_known is None or actor == victim:  # the world, a suicide, a fall
        out[(victim, v_side, "taken")] += harm
        _spread(out, gain, passive, a_side, "hold")
        return out
    if a_known == v_side:  # team damage or a team kill
        out[(actor, v_side, "team")] += harm
        _spread(out, gain, passive, a_side, "hold")
        return out
    out[(victim, v_side, "taken")] += harm
    weapon = e["weapon"] or ""
    if kind == "damage":
        out[(actor, a_side, "utility" if weapon in UTILITY_WEAPONS else "shooting")] += gain
        return out
    # A kill: the killer's side shares the gain.
    key = (e["round"], victim)
    by_part: dict[tuple[int, str], float] = defaultdict(float)
    for tick, attacker, w, hp in dealt.get(key, []):
        if tick <= e["tick"] and sides.get(attacker) == a_side and hp > 0:
            by_part[(attacker, "utility" if w in UTILITY_WEAPONS else "shooting")] += hp
    flashers: dict[int, float] = defaultdict(float)
    for tick, flasher, duration in blinds.get(key, []):
        left = duration - (e["tick"] - tick) / tickrate
        if tick <= e["tick"] and left >= shares.flash_min and sides.get(flasher) == a_side:
            flashers[flasher] += max(left, 1e-3)  # by the time still blind at the kill
    assister = flash_assist.get((e["round"], e["tick"], victim))
    if not flashers and assister is not None and sides.get(assister) == a_side:
        flashers[assister] = 1.0
    window = shares.trade_window * tickrate
    traded = [
        dead
        for tick, dead in kills_by.get((e["round"], victim), [])
        if e["tick"] - window <= tick < e["tick"] and sides.get(dead) == a_side
    ]
    present = {"final": shares.final}
    if by_part and shares.damage > 0:
        present["damage"] = shares.damage
    if flashers and shares.flash > 0:
        present["flash"] = shares.flash
    if traded and shares.trade > 0:
        present["trade"] = shares.trade
    total = sum(present.values())
    out[(actor, a_side, "utility" if weapon in UTILITY_WEAPONS else "shooting")] += (
        gain * present["final"] / total
    )
    if "damage" in present:
        dmg_total = sum(by_part.values())
        for (player, part), amount in by_part.items():
            out[(player, a_side, part)] += gain * present["damage"] / total * amount / dmg_total
    if "flash" in present:
        _spread(out, gain * present["flash"] / total, flashers, a_side, "utility")
    if "trade" in present:
        _spread(out, gain * present["trade"] / total, dict.fromkeys(traded, 1.0), a_side, "trade")
    return out


def per_player(credits: pl.DataFrame, rounds: pl.DataFrame) -> pl.DataFrame:
    """Each player's credit per round played, in percentage points, with its parts: `steamid`,
    `rounds`, `swing` and one column per part of `PARTS`. `rounds` is `round_player`-like
    (`steamid`, `round`); only the rounds with a ledger count, and a player credited in a round
    `rounds` does not list still has it counted, so no credit is lost."""
    with_ledger = credits.select("round").unique()
    played = (
        pl.concat(
            [
                rounds.select("steamid", pl.col("round").cast(pl.Int16)),
                credits.select("steamid", "round"),
            ]
        )
        .unique()
        .join(with_ledger, on="round", how="semi")
        .group_by("steamid")
        .agg(pl.len().alias("rounds"))
    )
    wide = (
        credits.group_by("steamid", "part")
        .agg(pl.col("credit").sum())
        .pivot("part", index="steamid", values="credit")
    )
    for part in PARTS:
        if part not in wide.columns:
            wide = wide.with_columns(pl.lit(0.0).alias(part))
    out = played.join(wide, on="steamid", how="left").with_columns(
        (pl.col(part).fill_null(0.0) * 100 / pl.col("rounds")).alias(part) for part in PARTS
    )
    return out.with_columns(pl.sum_horizontal(*PARTS).alias("swing")).select(
        "steamid", "rounds", "swing", *PARTS
    )


def _check(credits: pl.DataFrame) -> np.ndarray:
    """Each round's total credit (should be zero): for tests and the CLI."""
    return credits.group_by("round").agg(pl.col("credit").sum())["credit"].to_numpy()
