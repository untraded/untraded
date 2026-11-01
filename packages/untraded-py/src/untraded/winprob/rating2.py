# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The Untraded Rating 2.0: two numbers on one scale, what a match was worth and a level.

A player's credit per round in the ledger (`untraded.winprob.ledger`, percentage points, the hold
left out) is what their actions were worth. Over one match it is noisy: on 54 matches, a
player's K-D on half the rounds predicts their credit on the other half better than their credit
does. So the rating gives two answers, on one scale where 1.00 is the average player:

- **The match rating**: `1 + credit / s`, what the player's actions were worth in this match,
  with its margin (1.96 standard errors of the per-round credit). Faithful to what happened.
- **The level**: what the player is worth. The box score (kills, deaths and damage per round,
  `BOX_FEATURES`) predicts the credit through a ridge regression trained to **predict the credit
  of the rounds it did not see** (fitted on one half of each match against the credit of the
  other half, as basketball's BPM is fitted to plus-minus). The ledger can then correct that
  prediction as rounds add up:

      level = box + n / (n + k) * (credit - box)

  with `k` chosen by how well the level predicts the credit of unseen rounds (`ledger_rounds`;
  None when the box alone predicts best, as on halves of matches today). The level reads as the
  match rating to expect, so it sits closer to 1.00.

`s` is the credit per round worth 1.00, set so that the match rating spreads over the corpus's
player-matches as HLTV 1.0 does: a 1.20 reads as at HLTV. The box is centred per match, so the
average player of a match is 1.00 on both numbers.

Everything is fitted with matches held out (5 groups by a hash of the match id). The validation
compares the match rating, the level, the box alone, HLTV 1.0, the HLTV 2.0 approximation, ADR,
K-D and the rating 1 swing on predicting the other half of each match.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from untraded.ratings.hltv import rating_hltv_1, rating_hltv_2_approx
from untraded.winprob.ledger import UTILITY_WEAPONS

FORMAT_VERSION = 1
FEATURES = [
    "kpr",
    "dpr",
    "apr",
    "adr",
    "kast",
    "opening_kills",
    "opening_deaths",
    "flash_assists",
    "utility_damage",
    "trade_kills",
    "multikills",
    "survival",
]
"""The box score, per round played: kills, deaths, assists, damage (hundreds), KAST, opening
kills and deaths, flash assists, utility damage (hundreds), kills that trade a teammate, rounds
with two kills or more, rounds survived."""
BOX_FEATURES = ["kpr", "dpr", "adr"]
"""What the box predicts from: on 54 matches, kills, deaths and damage predict the credit of
unseen rounds best; more statistics overfit (`docs/winprob.md`)."""
TRADE_SECONDS = 5.0
LAMBDAS = (1.0, 10.0, 100.0, 1000.0, 10000.0)
LEDGER_ROUNDS: tuple[float | None, ...] = (12.0, 25.0, 50.0, 100.0, 200.0, 400.0, 800.0, None)
"""The values of `k` tried (None: the box alone)."""
FOLDS = 5
MIN_ROUNDS = 12
"""Player-matches shorter than this are left out of the fit and the validation."""
Z95 = 1.96


def round_stats(
    tables: Mapping[str, pl.DataFrame], derived: Mapping[str, pl.DataFrame]
) -> pl.DataFrame:
    """The box score of every player in every round (`steamid`, `round`, one column per
    `FEATURES` before averaging, and `kills`, `deaths`, `assists`, `damage` for the HLTV
    ratings)."""
    rp = derived["round_player"]
    deaths = derived["death"]
    trades = (
        deaths.filter(pl.col("trader").is_not_null(), pl.col("trade_delay_s") <= TRADE_SECONDS)
        .group_by("round", pl.col("trader").alias("steamid"))
        .agg(pl.len().cast(pl.Int32).alias("trade_kills"))
    )
    utility = (
        tables["damage"]
        .filter(
            ~pl.col("is_team_damage"),
            pl.col("attacker").is_not_null(),
            pl.col("weapon").is_in(list(UTILITY_WEAPONS)),
        )
        .group_by("round", pl.col("attacker").alias("steamid"))
        .agg(pl.col("dmg_health").sum().cast(pl.Float64).alias("utility_damage"))
    )
    traded = pl.col("death_trade_delay_s").is_not_null() & (
        pl.col("death_trade_delay_s") <= TRADE_SECONDS
    )
    return (
        rp.join(trades, on=["round", "steamid"], how="left")
        .join(utility, on=["round", "steamid"], how="left")
        .select(
            "steamid",
            "round",
            pl.col("kills").cast(pl.Float64),
            pl.col("deaths").cast(pl.Float64),
            pl.col("assists").cast(pl.Float64),
            pl.col("damage").cast(pl.Float64),
            pl.col("kills").cast(pl.Float64).alias("kpr"),
            pl.col("deaths").cast(pl.Float64).alias("dpr"),
            pl.col("assists").cast(pl.Float64).alias("apr"),
            (pl.col("damage") / 100).cast(pl.Float64).alias("adr"),
            ((pl.col("kills") > 0) | (pl.col("assists") > 0) | pl.col("survived") | traded)
            .cast(pl.Float64)
            .alias("kast"),
            pl.col("opening_kill").cast(pl.Float64).alias("opening_kills"),
            pl.col("opening_death").cast(pl.Float64).alias("opening_deaths"),
            pl.col("flash_assists").cast(pl.Float64),
            (pl.col("utility_damage").fill_null(0.0) / 100).alias("utility_damage"),
            pl.col("trade_kills").fill_null(0).cast(pl.Float64),
            (pl.col("kills") >= 2).cast(pl.Float64).alias("multikills"),
            pl.col("survived").cast(pl.Float64).alias("survival"),
        )
    )


def per_round(
    tables: Mapping[str, pl.DataFrame],
    derived: Mapping[str, pl.DataFrame],
    credits: pl.DataFrame,
    *,
    hold: bool = True,
) -> pl.DataFrame:
    """One row per player and round with a ledger: the box score (`round_stats`), `credit` (the
    ledger's, in percentage points; without the hold if `hold` is False, recentred so the round's
    players still average zero) and, when `derived` has it, `swing1` (rating 1's swing)."""
    rounds = credits.select("round").unique()
    if not hold:
        credits = credits.filter(pl.col("part") != "hold")
    per = credits.group_by("steamid", "round").agg((pl.col("credit").sum() * 100).alias("credit"))
    stats = round_stats(tables, derived).join(rounds, on="round", how="semi")
    out = stats.join(per, on=["steamid", "round"], how="left").with_columns(
        pl.col("credit").fill_null(0.0)
    )
    if not hold:
        out = out.with_columns(pl.col("credit") - pl.col("credit").mean().over("round"))
    if "swing" in derived:
        swing1 = (
            derived["swing"]
            .group_by("steamid", "round")
            .agg((pl.col("swing").cast(pl.Float64).sum() * 100).alias("swing1"))
        )
        out = out.join(swing1, on=["steamid", "round"], how="left").with_columns(
            pl.col("swing1").fill_null(0.0)
        )
    return out


def _hltv(group: pl.DataFrame) -> tuple[float, float]:
    """HLTV 1.0 and the 2.0 approximation of a set of a player's rounds."""
    n = group.height
    col = {c: group[c].to_numpy() for c in ("kills", "deaths", "assists", "damage", "kast")}
    kills, deaths = int(col["kills"].sum()), int(col["deaths"].sum())
    multi = {k: int((col["kills"] == k).sum()) for k in range(1, 6)}
    multi = {k: v for k, v in multi.items() if v}
    h1 = rating_hltv_1(n, kills, deaths, multi)
    h2 = rating_hltv_2_approx(
        n,
        kills,
        deaths,
        int(col["assists"].sum()),
        int(col["damage"].sum()),
        int(col["kast"].sum()),
    )
    return h1, h2


def halves(rounds: pl.DataFrame, match_id: str) -> pl.DataFrame:
    """Per player of a match: for each of `odd`, `even` and `all` rounds, the number of rounds,
    the mean credit, the box score averages, HLTV 1.0 and 2.0 (approx.), ADR, K-D and the rating
    1 swing. Columns `match_id`, `steamid`, `half`, `rounds`, `credit`, `FEATURES`, `hltv1`,
    `hltv2`, `kd`, `swing1`."""
    rows = []
    has_swing1 = "swing1" in rounds.columns
    for half, mask in (
        ("odd", pl.col("round") % 2 == 1),
        ("even", pl.col("round") % 2 == 0),
        ("all", pl.lit(True)),
    ):
        for (steamid,), group in rounds.filter(mask).group_by(["steamid"]):
            if group.is_empty():
                continue
            h1, h2 = _hltv(group)

            def mean(column: str, g: pl.DataFrame = group) -> float:
                return float(g[column].to_numpy().mean())

            row = {
                "match_id": match_id,
                "steamid": steamid,
                "half": half,
                "rounds": group.height,
                "credit": mean("credit"),
                **{f: mean(f) for f in FEATURES},
                "hltv1": h1,
                "hltv2": h2,
                "kd": mean("kpr") - mean("dpr"),
                "swing1": mean("swing1") if has_swing1 else float("nan"),
            }
            rows.append(row)
    return pl.DataFrame(rows)


def _fold(match_id: str) -> int:
    return int(hashlib.sha256(match_id.encode()).hexdigest(), 16) % FOLDS


@dataclass(frozen=True)
class Box:
    """The box-score estimator: a ridge regression on standardized `BOX_FEATURES`."""

    features: list[str]
    mean: list[float]
    scale: list[float]
    coef: list[float]
    intercept: float

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Predictions for rows of `x` (columns `features`, in order)."""
        z = (x - np.array(self.mean)) / np.array(self.scale)
        out: np.ndarray = z @ np.array(self.coef) + self.intercept
        return out


def _ridge(x: np.ndarray, y: np.ndarray, w: np.ndarray, lam: float, features: Sequence[str]) -> Box:
    mean = np.average(x, axis=0, weights=w)
    scale = np.sqrt(np.average((x - mean) ** 2, axis=0, weights=w))
    scale[scale == 0] = 1.0
    z = (x - mean) / scale
    ym = float(np.average(y, weights=w))
    zw = z * w[:, None]
    penalty = lam * w.sum() / len(w) * np.eye(z.shape[1])
    coef = np.linalg.solve(z.T @ zw + penalty, zw.T @ (y - ym))
    return Box(
        list(features),
        [float(v) for v in mean],
        [float(v) for v in scale],
        [float(v) for v in coef],
        ym,
    )


def _cross_pairs(frame: pl.DataFrame) -> pl.DataFrame:
    """Each half of each player-match (MIN_ROUNDS or more in the match) next to the other half:
    this half's columns, and `other_credit`, `other_hltv1`, `other_rounds` from the other."""
    whole = frame.filter(pl.col("half") == "all", pl.col("rounds") >= MIN_ROUNDS).select(
        "match_id", "steamid"
    )
    parts = frame.filter(pl.col("half") != "all").join(
        whole, on=["match_id", "steamid"], how="semi"
    )
    other = parts.select(
        "match_id",
        "steamid",
        pl.when(pl.col("half") == "odd")
        .then(pl.lit("even"))
        .otherwise(pl.lit("odd"))
        .alias("half"),
        *(pl.col(c).alias(f"other_{c}") for c in ("credit", "hltv1", "rounds")),
    )
    return parts.join(other, on=["match_id", "steamid", "half"])


def _keys(frame: pl.DataFrame) -> list[str]:
    """A match's half (or the match, for whole rows): what a value is centred within. The unit
    separator cannot occur in a match id, so two keys never collide."""
    return [
        f"{m}\x1f{h}"
        for m, h in zip(frame["match_id"].to_list(), frame["half"].to_list(), strict=True)
    ]


def _centred(values: np.ndarray, groups: Sequence[str], weights: np.ndarray) -> np.ndarray:
    """`values` minus their weighted mean within each group (a match, or a match's half)."""
    frame = pl.DataFrame({"g": list(groups), "v": values.astype(float), "w": weights.astype(float)})
    mean = (pl.col("v") * pl.col("w")).sum().over("g") / pl.col("w").sum().over("g")
    out: np.ndarray = frame.select(pl.col("v") - mean).to_series().to_numpy()
    return out


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return float("nan")
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def _box_cross_fitted(pairs: pl.DataFrame, lam: float) -> np.ndarray:
    """The box's prediction for every half, from a box fitted without its match, centred per
    match half (so the average player of a half is zero, as in the ledger)."""
    x = pairs.select(BOX_FEATURES).to_numpy()
    y = pairs["other_credit"].to_numpy()
    w = pairs["rounds"].to_numpy().astype(float)
    folds = np.array([_fold(m) for m in pairs["match_id"].to_list()])
    pred = np.zeros(len(y))
    for k in range(FOLDS):
        inside = folds == k
        if not inside.any() or inside.all():
            continue
        pred[inside] = _ridge(x[~inside], y[~inside], w[~inside], lam, BOX_FEATURES).predict(
            x[inside]
        )
    return _centred(pred, _keys(pairs), w)


@dataclass(frozen=True)
class RatingModel:
    version: str
    """The rating's version, e.g. `2.0`."""
    model: str
    """The win-probability model behind the ledger."""
    shares: dict[str, float]
    """The ledger's shares (`untraded.winprob.ledger.Shares`)."""
    hold: bool
    """Whether the ledger's hold (the clock, the round's end) counts."""
    points_per_rating: float
    """`s`: percentage points of credit per round worth 1.00 of rating."""
    box: Box
    lam: float
    ledger_rounds: float | None
    """`k`: after `k` rounds, the ledger weighs as much as the box in the level; chosen on the
    corpus by how well the level predicts the credit of unseen rounds. None when the box alone
    predicts best: the level is then the box until the corpus says otherwise."""
    trained_on: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)

    def match_rating(self, credit: float) -> float:
        """The match rating of a credit per round (percentage points)."""
        return 1 + credit / self.points_per_rating

    def level(self, box: float, credit: float, rounds: int) -> float:
        """The level in credit per round: the box's prediction, moved towards the ledger's credit
        by `rounds / (rounds + k)`."""
        return _level(box, credit, rounds, self.ledger_rounds)

    def level_rating(self, box: float, credit: float, rounds: int) -> float:
        """The level on the rating's scale (1.00 = the average player)."""
        return 1 + self.level(box, credit, rounds) / self.points_per_rating

    def rate_match(self, rounds: pl.DataFrame) -> pl.DataFrame:
        """Every player of a match, from `per_round` rows: `steamid`, `rounds`, `credit` (per
        round, percentage points), `rating` (the match rating), `margin` (half-width of its 95 %
        interval; null under 2 rounds), `box` (the box's prediction, centred on the match) and
        `level` (the level this match alone gives, on the rating's scale)."""
        if rounds.is_empty():
            return pl.DataFrame(
                schema={
                    "steamid": pl.UInt64,
                    "rounds": pl.UInt32,
                    "credit": pl.Float64,
                    "rating": pl.Float64,
                    "margin": pl.Float64,
                    "box": pl.Float64,
                    "level": pl.Float64,
                }
            )
        agg = rounds.group_by("steamid").agg(
            pl.len().alias("rounds"),
            pl.col("credit").mean(),
            pl.col("credit").std().alias("sd"),
            *(pl.col(f).mean() for f in BOX_FEATURES),
        )
        w = agg["rounds"].to_numpy().astype(float)
        box = self.box.predict(agg.select(self.box.features).to_numpy())
        box = box - np.average(box, weights=w)
        credit = agg["credit"].to_numpy()
        n = agg["rounds"].to_numpy()
        s = self.points_per_rating
        return agg.select("steamid", "rounds", "credit").with_columns(
            pl.Series("rating", [self.match_rating(c) for c in credit]),
            (Z95 * agg["sd"] / agg["rounds"].cast(pl.Float64).sqrt() / s).alias("margin"),
            pl.Series("box", box),
            pl.Series(
                "level",
                [self.level_rating(b, c, int(r)) for b, c, r in zip(box, credit, n, strict=True)],
            ),
        )

    def to_json(self) -> str:
        data = _finite({"format": FORMAT_VERSION, **asdict(self)})
        return json.dumps(data, indent=2, allow_nan=False)

    def save(self, path: Path) -> None:
        path.write_text(self.to_json() + "\n", encoding="utf-8", newline="\n")

    @classmethod
    def from_json(cls, text: str) -> RatingModel:
        """Reads a rating file, checking every number it computes with (a bad file is refused,
        never silently turned into wrong ratings)."""

        def refuse(constant: str) -> float:
            raise ValueError(f"the rating file holds {constant}")

        try:
            data = json.loads(text, parse_constant=refuse)
            if not isinstance(data, dict) or data.pop("format", None) != FORMAT_VERSION:
                raise ValueError("unknown rating format")
            data["box"] = Box(**data["box"])
            model = cls(**data)
        except (TypeError, KeyError, AttributeError) as error:
            raise ValueError(f"malformed rating file: {error}") from error
        box = model.box
        if box.features != BOX_FEATURES:
            raise ValueError(f"the rating's box must read {BOX_FEATURES}")
        arrays = (box.mean, box.scale, box.coef)
        if any(not isinstance(a, list) or len(a) != len(BOX_FEATURES) for a in arrays):
            raise ValueError("the rating's box needs one number per feature")
        numbers = [*box.mean, *box.scale, *box.coef, box.intercept, model.points_per_rating]
        numbers += [model.lam]
        if model.ledger_rounds is not None:
            numbers.append(model.ledger_rounds)
        if not all(_number(v) for v in numbers):
            raise ValueError("the rating needs finite numbers")
        if min(box.scale) <= 0 or model.points_per_rating <= 0:
            raise ValueError("the rating's scales must be positive")
        if model.ledger_rounds is not None and model.ledger_rounds <= 0:
            raise ValueError("the rating's ledger rounds must be positive")
        return model


def _number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _level(box: float, credit: float, rounds: int, k: float | None) -> float:
    weight = 0.0 if k is None else rounds / (rounds + k)
    return box + weight * (credit - box)


def _finite(value: Any) -> Any:
    """`value` with every non-finite float as None, so that it is valid JSON."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_finite(v) for v in value]
    return value


def _sb(r: float) -> float:
    return 2 * r / (1 + r) if math.isfinite(r) and r > -1 else float("nan")


def _variances(pairs: pl.DataFrame, box: np.ndarray) -> tuple[float, float]:
    """A diagnostic: sigma^2 (a round's credit around the player's level) from the gap between a
    player's two halves, and tau^2 from the covariance of the two halves' residuals from the box.
    `sigma^2 / tau^2` would be `k` if the box's errors and the credit's noise were independent;
    they are not (both come from the same rounds), so `k` is fitted instead (`fit`)."""
    frame = pairs.with_columns(pl.Series("box", box)).with_columns(
        (pl.col("credit") - pl.col("box")).alias("residual")
    )
    odd = frame.filter(pl.col("half") == "odd").select(
        "match_id",
        "steamid",
        pl.col("credit").alias("c1"),
        pl.col("residual").alias("r1"),
        pl.col("rounds").alias("n1"),
    )
    even = frame.filter(pl.col("half") == "even").select(
        "match_id",
        "steamid",
        pl.col("credit").alias("c2"),
        pl.col("residual").alias("r2"),
        pl.col("rounds").alias("n2"),
    )
    both = odd.join(even, on=["match_id", "steamid"])
    gap = (both["c1"] - both["c2"]).to_numpy()
    harmonic = (1 / both["n1"].cast(pl.Float64) + 1 / both["n2"].cast(pl.Float64)).to_numpy()
    sigma2 = float(np.mean(gap**2 / harmonic))
    r1, r2 = both["r1"].to_numpy(), both["r2"].to_numpy()
    tau2 = float(np.mean((r1 - r1.mean()) * (r2 - r2.mean())))
    return sigma2, max(tau2, 0.0)


def fit(
    frames: Sequence[pl.DataFrame],
    *,
    version: str,
    model: str,
    shares: Mapping[str, float],
    hold: bool = False,
    trained_on: Mapping[str, Any] | None = None,
) -> RatingModel:
    """Fits the rating on `halves` frames (one per match, built with the same `hold`): the
    box's penalty and the level's `k`, both by the squared error of predicting the other half of
    each match with matches held out; then the box on every match and the scale."""
    frame = pl.concat(frames)
    pairs = _cross_pairs(frame)
    if pairs.height < 20:
        raise ValueError("not enough player-matches to fit the rating")
    target = pairs["other_credit"].to_numpy()
    x = pairs.select(BOX_FEATURES).to_numpy()
    w = pairs["rounds"].to_numpy().astype(float)
    # The penalty by squared error, not correlation: the level adds the box to the credit, so
    # the box's scale matters, and a correlation would not see a box shrunk to nothing.
    errors = {
        lam: float(np.average((_box_cross_fitted(pairs, lam) - target) ** 2, weights=w))
        for lam in LAMBDAS
    }
    lam = min(errors, key=lambda v: errors[v])
    box = _ridge(x, target, w, lam, BOX_FEATURES)
    held_out_box = _box_cross_fitted(pairs, lam)
    credit = pairs["credit"].to_numpy()
    n = pairs["rounds"].to_numpy()
    k_errors: dict[float | None, float] = {}
    for k in LEDGER_ROUNDS:
        level = np.array(
            [_level(b, c, int(r), k) for b, c, r in zip(held_out_box, credit, n, strict=True)]
        )
        k_errors[k] = float(np.average((level - target) ** 2, weights=w))
    k_best = min(k_errors, key=lambda v: k_errors[v])
    whole = frame.filter(pl.col("half") == "all", pl.col("rounds") >= MIN_ROUNDS)
    s = float(
        np.std(whole["credit"].to_numpy(), ddof=1) / np.std(whole["hltv1"].to_numpy(), ddof=1)
    )
    if not math.isfinite(s) or s <= 0:
        raise ValueError("the corpus gives no scale: the credit or HLTV 1.0 does not vary")
    sigma2, tau2 = _variances(pairs, held_out_box)
    rating = RatingModel(
        version=version,
        model=model,
        shares=dict(shares),
        hold=hold,
        points_per_rating=round(s, 4),
        box=box,
        lam=lam,
        ledger_rounds=k_best,
        trained_on={
            **dict(trained_on or {}),
            "player_matches": whole.height,
            "matches": whole["match_id"].n_unique(),
            "trained": dt.date.today().isoformat(),
        },
    )
    validation = validate(frame, rating)
    validation["level_error_by_ledger_rounds"] = {
        ("box only" if k is None else str(int(k))): round(e, 3) for k, e in k_errors.items()
    }
    validation["variances"] = {
        "round": round(sigma2, 2),
        "level_around_box": round(tau2, 2),
        "their_ratio": round(sigma2 / tau2, 1) if tau2 > 0 else None,
    }
    return RatingModel(**{**rating.__dict__, "validation": validation})


METRICS = ("match", "level", "box", "hltv1", "hltv2", "adr", "kd", "swing1")


def _metric_values(pairs: pl.DataFrame, rating: RatingModel) -> dict[str, np.ndarray]:
    """Each metric on each half (the box cross-fitted, so it never sees the match)."""
    box = _box_cross_fitted(pairs, rating.lam)
    credit = pairs["credit"].to_numpy()
    n = pairs["rounds"].to_numpy()
    level = np.array([rating.level(b, c, int(r)) for b, c, r in zip(box, credit, n, strict=True)])
    return {
        "match": credit,
        "level": level,
        "box": box,
        "hltv1": pairs["hltv1"].to_numpy(),
        "hltv2": pairs["hltv2"].to_numpy(),
        "adr": pairs["adr"].to_numpy(),
        "kd": pairs["kd"].to_numpy(),
        "swing1": pairs["swing1"].to_numpy(),
    }


def _bootstrap_gain(
    a: np.ndarray,
    b: np.ndarray,
    target: np.ndarray,
    matches: Sequence[str],
    resamples: int = 1000,
) -> dict[str, float]:
    """corr(a, target) - corr(b, target), with a 95 % interval from resampling matches."""
    ids = sorted(set(matches))
    index: dict[str, list[int]] = {m: [] for m in ids}
    for i, m in enumerate(matches):
        index[m].append(i)
    rng = np.random.default_rng(0)
    draws = []
    for _ in range(resamples):
        rows = np.concatenate([index[ids[j]] for j in rng.integers(0, len(ids), len(ids))])
        draws.append(_corr(a[rows], target[rows]) - _corr(b[rows], target[rows]))
    low, high = np.nanpercentile(draws, [2.5, 97.5])
    gain = _corr(a, target) - _corr(b, target)
    return {"gain": round(gain, 4), "low": round(float(low), 4), "high": round(float(high), 4)}


def validate(frame: pl.DataFrame, rating: RatingModel) -> dict[str, Any]:
    """How well each metric on one half of a match predicts the other half: the ledger's credit
    there, and HLTV 1.0 there (a target the ledger does not build); the level's gain over HLTV
    1.0 and the match rating, with intervals; the split-half reliability of the match rating and
    of the level; and how much of each metric is the player's from one match to the next."""
    pairs = _cross_pairs(frame)
    values = _metric_values(pairs, rating)
    matches = pairs["match_id"].to_list()
    out: dict[str, Any] = {"player_halves": pairs.height}
    for target in ("credit", "hltv1"):
        t = pairs[f"other_{target}"].to_numpy()
        out[f"predicts_other_half_{target}"] = {
            name: round(_corr(v, t), 4) for name, v in values.items()
        }
        out[f"level_gain_{target}"] = {
            other: _bootstrap_gain(values["level"], values[other], t, matches)
            for other in ("match", "hltv1", "kd")
        }
    halves_frame = pairs.select("match_id", "steamid", "half").with_columns(
        pl.Series("match", values["match"]), pl.Series("level", values["level"])
    )
    odd = halves_frame.filter(pl.col("half") == "odd")
    even = halves_frame.filter(pl.col("half") == "even")
    both = odd.join(even, on=["match_id", "steamid"], suffix="_even")
    out["split_half"] = {
        name: round(_sb(_corr(both[name].to_numpy(), both[f"{name}_even"].to_numpy())), 4)
        for name in ("match", "level")
    }
    out["between_matches"] = _between_matches(frame, rating)
    return out


def _between_matches(frame: pl.DataFrame, rating: RatingModel) -> dict[str, float]:
    """ICC(1) of each metric per match, for players with 3 matches or more."""
    whole = frame.filter(pl.col("half") == "all", pl.col("rounds") >= MIN_ROUNDS)
    w = whole["rounds"].to_numpy().astype(float)
    box = _centred(
        rating.box.predict(whole.select(BOX_FEATURES).to_numpy()), whole["match_id"].to_list(), w
    )
    credit = whole["credit"].to_numpy()
    n = whole["rounds"].to_numpy()
    values = {
        "match": credit,
        "level": np.array(
            [rating.level(b, c, int(r)) for b, c, r in zip(box, credit, n, strict=True)]
        ),
        "hltv1": whole["hltv1"].to_numpy(),
        "adr": whole["adr"].to_numpy(),
        "kd": whole["kd"].to_numpy(),
    }
    players = whole["steamid"].to_list()
    counts: dict[int, int] = {}
    for p in players:
        counts[p] = counts.get(p, 0) + 1
    recurring = [p for p, c in counts.items() if c >= 3]
    ids = np.array(players)
    out: dict[str, float] = {"players": float(len(recurring))}
    for name, v in values.items():
        out[name] = round(_icc([v[ids == p] for p in recurring]), 4)
    return out


def _icc(groups: Sequence[np.ndarray]) -> float:
    if len(groups) < 2:
        return float("nan")
    n_total = sum(len(g) for g in groups)
    k = len(groups)
    grand = float(np.concatenate(groups).mean())
    between = sum(len(g) * (g.mean() - grand) ** 2 for g in groups) / (k - 1)
    within = sum(((g - g.mean()) ** 2).sum() for g in groups) / (n_total - k)
    n0 = (n_total - sum(len(g) ** 2 for g in groups) / n_total) / (k - 1)
    denominator = between + (n0 - 1) * within
    return float((between - within) / denominator) if denominator > 0 else float("nan")
