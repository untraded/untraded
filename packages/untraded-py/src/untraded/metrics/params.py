# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Every adjustable parameter, with its default, unit and meaning (ADR 0007).

Metric parameters are applied when a metric is computed (`compute(..., params=...)`). Derivation
parameters are applied when the round model is built: changing one means deriving again.
`calibrate` marks the v0 thresholds still to calibrate on demos from consenting high-level
players (🎯, ADR 0010).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from untraded.derive.buys import BuyThresholds
from untraded.derive.players import SETUP_OFFSET_S
from untraded.metrics.registry import ParamValue

Stage = Literal["metric", "derive"]


@dataclass(frozen=True)
class Parameter:
    id: str
    default: ParamValue
    unit: str
    doc: str
    calibrate: bool = False
    stage: Stage = "metric"


_BUY = BuyThresholds()

PARAMETERS: dict[str, Parameter] = {
    p.id: p
    for p in (
        Parameter(
            "trade.window_s",
            5.0,
            "s",
            "Trade window W: a death is traded when a teammate kills the killer within W "
            "seconds, the same tick included (HLTV and CS Demo Manager convention).",
        ),
        Parameter(
            "trade.window_w3_s",
            3.0,
            "s",
            "Shorter trade window of the `_w3` variants, for tighter trades.",
        ),
        Parameter(
            "trade.opportunity_distance",
            1000.0,
            "units",
            "A living teammate of the victim within this straight-line distance of the killer "
            "had a trade opportunity.",
            calibrate=True,
        ),
        Parameter(
            "isolation.radius",
            1000.0,
            "units",
            "An untraded death is isolated when the nearest living teammate is farther than this.",
            calibrate=True,
        ),
        Parameter(
            "assist.flash_weight",
            0.5,
            "ratio",
            "Weight of a flash assist in `base.assist_score`, an assist weighing 1.",
        ),
        Parameter(
            "kast.count_flash_assist",
            False,
            "boolean",
            "Whether a flash assist alone makes a round count for KAST.",
        ),
        Parameter(
            "flash.min_blind_s",
            1.0,
            "s",
            "Minimum blind duration for a blind to count as a flash (counts only; blind times "
            "keep every blind).",
        ),
        Parameter(
            "pos.recurring_death_share",
            0.25,
            "ratio",
            "Share of the player's untraded deaths on a map and side that makes a zone recurring.",
            calibrate=True,
        ),
        Parameter(
            "pos.recurring_min_rounds",
            8,
            "rounds",
            "Rounds the player must have played on a map and side before a zone can be recurring.",
            calibrate=True,
        ),
        Parameter(
            "setup.offset_s",
            SETUP_OFFSET_S,
            "s",
            "The setup zone is read this long after freeze-time end (`pos.setup_zone_t20`).",
            stage="derive",
        ),
        Parameter(
            "buy.eco_max",
            _BUY.eco_max,
            "$",
            "A team buy is an eco at or below this average equipment value per player, at "
            "freeze-time end + 7 s.",
            calibrate=True,
            stage="derive",
        ),
        Parameter(
            "buy.full_min_ct",
            _BUY.full_min_ct,
            "$",
            "A CT buy is a full buy at or above this average equipment value per player.",
            calibrate=True,
            stage="derive",
        ),
        Parameter(
            "buy.full_min_t",
            _BUY.full_min_t,
            "$",
            "A T buy is a full buy at or above this average equipment value per player.",
            calibrate=True,
            stage="derive",
        ),
    )
}
