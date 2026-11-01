# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Choosing the ledger's shares on a corpus: the split that measures players most reliably.

The shares cannot change what a side earns in a round (the ledger adds up to its result), only
how it is split between teammates. So the criterion looks at each player's credit **relative to
their team**: every round, a player's credit minus the average credit of their side. A split that
credits the right players gives a relative credit that holds from one half of a match to the
other; a split that credits at random does not.

- `split_half`: within each match, the correlation of a player's relative credit per round on
  odd and on even rounds, over all player-matches, stepped up to the whole match
  (Spearman-Brown). Every player-match counts, so it is the main criterion.
- `between_matches`: for players with several matches, the share of the variance of their
  relative credit per match that comes from the player (ICC(1)). Few players recur in
  matchmaking, so it is reported, not optimized.

`choose` searches the shares one at a time (coordinate ascent over `GRID`), keeping a change only
when it gains more than `TOLERANCE`: near-ties stay at the starting point, Leetify's published
split. `cross_check` chooses on half the matches and scores on the other half, so the gain is
measured where it was not chosen.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import polars as pl

from untraded.winprob.ledger import DEFAULT_SHARES, Prepared, Shares, credit

GRID: Mapping[str, tuple[float, ...]] = {
    "damage": (0.15, 0.3, 0.45, 0.6),
    "flash": (0.0, 0.05, 0.1, 0.15, 0.25),
    "trade": (0.0, 0.1, 0.2, 0.3),
    "plant": (0.25, 0.5, 0.75, 1.0),
    "defuse": (0.25, 0.5, 0.7, 1.0),
    "trade_window": (3.0, 4.0, 5.0),
}
"""The values tried for each share. The killer's share is what the others leave of 1."""
MIN_FINAL = 0.1
"""The killer always keeps at least this share of a kill."""
TOLERANCE = 0.005
"""A change of shares is kept only if it gains more split-half reliability than this."""
MIN_ROUNDS = 12
"""Player-matches shorter than this are left out of the criteria."""
PASSES = 2


@dataclass(frozen=True)
class Match:
    """One match for the study: its prepared ledger and who played which round on which side
    (`steamid`, `round`, `side`, as in `round_player`)."""

    prepared: Prepared
    played: pl.DataFrame
    match_id: str


def played(tables: Mapping[str, pl.DataFrame]) -> pl.DataFrame:
    """Who played which round on which side, from `player_tick` (`steamid`, `round`, `side`)."""
    return (
        tables["player_tick"]
        .filter(pl.col("steamid").is_not_null(), pl.col("side").cast(pl.String).is_in(["CT", "T"]))
        .select("steamid", "round", pl.col("side").cast(pl.String))
        .unique(["steamid", "round"], keep="first")
    )


def relative(credits: pl.DataFrame, played: pl.DataFrame) -> pl.DataFrame:
    """Each player's credit per round minus their side's average that round (`steamid`,
    `round`, `relative`): the part of the round's result that the split gives them in
    particular. Rounds without a ledger are left out."""
    rounds = credits.select("round").unique()
    per = (
        played.select("steamid", pl.col("round").cast(pl.Int16), pl.col("side").cast(pl.String))
        .join(rounds, on="round", how="semi")
        .join(
            credits.group_by("steamid", "round").agg(pl.col("credit").sum()),
            on=["steamid", "round"],
            how="left",
        )
        .with_columns(pl.col("credit").fill_null(0.0))
    )
    return per.select(
        "steamid",
        "round",
        (pl.col("credit") - pl.col("credit").mean().over("round", "side")).alias("relative"),
    )


def _per_player_match(rel: pl.DataFrame) -> pl.DataFrame:
    return (
        rel.with_columns((pl.col("round") % 2).alias("half"))
        .group_by("match_id", "steamid")
        .agg(
            pl.len().alias("rounds"),
            pl.col("relative").mean().alias("all"),
            pl.col("relative").filter(pl.col("half") == 0).mean().alias("odd"),
            pl.col("relative").filter(pl.col("half") == 1).mean().alias("even"),
        )
        .filter(pl.col("rounds") >= MIN_ROUNDS)
        .drop_nulls()
    )


def split_half(rel: pl.DataFrame) -> float:
    """Spearman-Brown split-half reliability of the relative credit (`rel` has `match_id`,
    `steamid`, `round`, `relative`)."""
    per = _per_player_match(rel)
    if per.height < 3:
        return float("nan")
    return _sb(per["odd"].to_numpy(), per["even"].to_numpy())


def _sb(odd: np.ndarray, even: np.ndarray) -> float:
    r = float(np.corrcoef(odd, even)[0, 1])
    return 2 * r / (1 + r) if math.isfinite(r) and r > -1 else float("nan")


def split_half_gain(
    rel: pl.DataFrame, reference: pl.DataFrame, resamples: int = 1000, seed: int = 0
) -> dict[str, float]:
    """How much more split-half reliable `rel` is than `reference` (same matches), with a 95 %
    interval from resampling matches: a gain whose interval excludes zero is real."""
    a = _per_player_match(rel).rename({"odd": "a_odd", "even": "a_even"})
    b = _per_player_match(reference).rename({"odd": "b_odd", "even": "b_even"})
    both = a.select("match_id", "steamid", "a_odd", "a_even").join(
        b.select("match_id", "steamid", "b_odd", "b_even"), on=["match_id", "steamid"]
    )
    ids = sorted(set(both["match_id"].to_list()))
    if len(ids) < 2:
        return {"gain": float("nan"), "low": float("nan"), "high": float("nan")}
    index: dict[str, list[int]] = {m: [] for m in ids}
    for i, m in enumerate(both["match_id"].to_list()):
        index[m].append(i)
    cols = {c: both[c].to_numpy() for c in ("a_odd", "a_even", "b_odd", "b_even")}
    gain = _sb(cols["a_odd"], cols["a_even"]) - _sb(cols["b_odd"], cols["b_even"])
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(resamples):
        rows = np.concatenate([index[ids[j]] for j in rng.integers(0, len(ids), len(ids))])
        draws.append(
            _sb(cols["a_odd"][rows], cols["a_even"][rows])
            - _sb(cols["b_odd"][rows], cols["b_even"][rows])
        )
    low, high = np.nanpercentile(draws, [2.5, 97.5])
    return {"gain": round(gain, 4), "low": round(float(low), 4), "high": round(float(high), 4)}


def between_matches(rel: pl.DataFrame, min_matches: int = 3) -> float:
    """ICC(1) of the relative credit per match, for players with `min_matches` or more: the share
    of its variance that is the player's (nan when fewer than two such players)."""
    per = _per_player_match(rel)
    counts = per.group_by("steamid").agg(pl.len().alias("n"))
    kept = per.join(counts.filter(pl.col("n") >= min_matches), on="steamid", how="semi")
    groups = [g["all"].to_numpy() for _, g in kept.group_by("steamid")]
    if len(groups) < 2:
        return float("nan")
    n_total = sum(len(g) for g in groups)
    grand = float(np.concatenate(groups).mean())
    k = len(groups)
    between = sum(len(g) * (g.mean() - grand) ** 2 for g in groups) / (k - 1)
    within = sum(((g - g.mean()) ** 2).sum() for g in groups) / (n_total - k)
    n0 = (n_total - sum(len(g) ** 2 for g in groups) / n_total) / (k - 1)
    denominator = between + (n0 - 1) * within
    return float((between - within) / denominator) if denominator > 0 else float("nan")


def relative_credits(
    matches: Sequence[Match],
    shares: Shares,
    keep: Callable[[pl.DataFrame], pl.DataFrame] | None = None,
) -> pl.DataFrame:
    """The relative credits of every match under `shares` (`keep` filters each match's credits
    first, for ablations)."""
    frames = []
    for m in matches:
        credits = credit(m.prepared, shares)
        if keep is not None:
            credits = keep(credits)
        frames.append(
            relative(credits, m.played).with_columns(pl.lit(m.match_id).alias("match_id"))
        )
    return pl.concat(frames)


def score(
    matches: Sequence[Match],
    shares: Shares,
    keep: Callable[[pl.DataFrame], pl.DataFrame] | None = None,
) -> dict[str, float]:
    rel = relative_credits(matches, shares, keep)
    return {
        "split_half": round(split_half(rel), 4),
        "between_matches": round(between_matches(rel), 4),
    }


def _with(shares: Shares, name: str, value: float) -> Shares | None:
    """`shares` with one value changed, the killer's share taking what the others leave; None
    when that leaves the killer less than `MIN_FINAL`."""
    changed = replace(shares, **{name: value})
    if name in ("damage", "flash", "trade"):
        final = 1 - changed.damage - changed.flash - changed.trade
        if final < MIN_FINAL - 1e-9:
            return None
        changed = replace(changed, final=round(final, 4))
    return changed


def _normalized(shares: Shares) -> Shares:
    """`shares` with the kill's shares adding up to 1 (the killer's taking the rest)."""
    total = shares.final + shares.damage + shares.flash + shares.trade
    return replace(
        shares,
        final=round(shares.final / total, 4),
        damage=round(shares.damage / total, 4),
        flash=round(shares.flash / total, 4),
        trade=round(shares.trade / total, 4),
    )


def choose(
    matches: Sequence[Match],
    start: Shares = DEFAULT_SHARES,
    grid: Mapping[str, Sequence[float]] = GRID,
    passes: int = PASSES,
) -> tuple[Shares, list[dict[str, Any]]]:
    """Coordinate ascent on the split-half reliability, from `start`: each share in turn takes the
    value of `grid` that scores best, if it beats the current one by more than `TOLERANCE`.
    Returns the shares and every value tried."""
    current = _normalized(start)
    best = score(matches, current)["split_half"]
    steps: list[dict[str, Any]] = []
    for _ in range(passes):
        moved = False
        for name, values in grid.items():
            tried = {}
            for value in values:
                candidate = _with(current, name, value)
                if candidate is None:
                    continue
                tried[value] = (
                    best if candidate == current else score(matches, candidate)["split_half"]
                )
            top = max(tried, key=lambda v: tried[v])
            kept = tried[top] > best + TOLERANCE
            steps.append({"share": name, "tried": tried, "kept": top if kept else None})
            if kept:
                changed = _with(current, name, top)
                assert changed is not None
                current, best, moved = changed, tried[top], True
        if not moved:
            break
    return current, steps


def _half(match_id: str) -> int:
    return int(hashlib.sha256(match_id.encode()).hexdigest(), 16) % 2


def cross_check(
    matches: Sequence[Match], start: Shares = DEFAULT_SHARES, **kwargs: Any
) -> list[dict[str, Any]]:
    """Shares chosen on each half of the matches (split by a hash of the match id), scored on the
    other half against `start`: the gain where the shares were not chosen."""
    out = []
    for half in (0, 1):
        fit = [m for m in matches if _half(m.match_id) == half]
        test = [m for m in matches if _half(m.match_id) != half]
        if not fit or not test:
            continue
        chosen, _ = choose(fit, start, **kwargs)
        out.append(
            {
                "chosen_on": len(fit),
                "scored_on": len(test),
                "shares": chosen,
                "chosen": score(test, chosen),
                "start": score(test, _normalized(start)),
            }
        )
    return out


ABLATIONS: Mapping[
    str, tuple[Callable[[Shares], Shares], Callable[[pl.DataFrame], pl.DataFrame]]
] = {
    "no hold": (lambda s: s, lambda c: c.filter(pl.col("part") != "hold")),
    "no trade share": (lambda s: _with(s, "trade", 0.0) or s, lambda c: c),
    "no flash share": (lambda s: _with(s, "flash", 0.0) or s, lambda c: c),
    "killer takes all": (
        lambda s: replace(s, final=1.0, damage=0.0, flash=0.0, trade=0.0),
        lambda c: c,
    ),
}
"""Variants of the chosen shares, to show what each piece of the ledger brings: without the hold
(the clock and the round's end), without the trade or flash share, and with the killer alone."""


def ablations(matches: Sequence[Match], shares: Shares) -> dict[str, dict[str, Any]]:
    """The criteria of `shares` and of each variant, with the variant's split-half gain over
    `shares` and its 95 % interval."""
    reference = relative_credits(matches, shares)
    out: dict[str, dict[str, Any]] = {
        "chosen": {
            "split_half": round(split_half(reference), 4),
            "between_matches": round(between_matches(reference), 4),
        }
    }
    for name, (change, keep) in ABLATIONS.items():
        rel = relative_credits(matches, change(shares), keep)
        out[name] = {
            "split_half": round(split_half(rel), 4),
            "between_matches": round(between_matches(rel), 4),
            "gain_over_chosen": split_half_gain(rel, reference),
        }
    return out


def decide(start: Shares, chosen: Shares, checks: Sequence[Mapping[str, Any]]) -> Shares:
    """The shares to publish: `chosen` only if, on the matches it was not chosen on, it beats the
    starting shares by more than `TOLERANCE` on average; otherwise the starting shares (a gain
    that does not hold out of sample is noise)."""
    gains = [c["chosen"]["split_half"] - c["start"]["split_half"] for c in checks]
    if gains and all(math.isfinite(g) for g in gains) and sum(gains) / len(gains) > TOLERANCE:
        return chosen
    return _normalized(start)
