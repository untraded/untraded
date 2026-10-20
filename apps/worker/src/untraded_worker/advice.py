# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""A session's priorities (`advice`), computed right after its report by the `session` job.

The rules are those of `untraded.advice`: they compare the session with the reference the
report used (the player's own days, or their level) and look at the days before it for patterns.
The three costliest findings are kept, with their evidence; each event gets the tick to jump to
in the demo, `LEAD` before it happened (`demo_gototick`).
"""

from __future__ import annotations

import datetime as dt
import json
import math
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

import polars as pl
import psycopg
from psycopg.types.json import Jsonb

from untraded.advice import Finding, find, prioritize
from untraded.metrics import REGISTRY, Dataset

LEAD = dt.timedelta(seconds=5)
"""How long before the event the demo starts: enough to see it coming."""


def _clean(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def evidence_rows(
    found: Finding, match_ids: Mapping[str, uuid.UUID], tickrates: Mapping[str, float]
) -> list[dict[str, Any]]:
    """The finding's events for the clients: our match id, and the tick to jump to."""
    rows = []
    for event in found.evidence.iter_rows(named=True):
        sha = event["match_id"]
        lead = int(LEAD.total_seconds() * tickrates.get(sha, 64.0))
        row = {k: _clean(v) for k, v in event.items() if k != "match_id"}
        row["match_id"] = str(match_ids[sha])
        row["goto_tick"] = max(0, int(event["tick"]) - lead)
        rows.append(row)
    return rows


def advise(
    conn: psycopg.Connection[Any],
    steam_id: int,
    session_id: uuid.UUID,
    span: tuple[dt.datetime, dt.datetime],
    session: Sequence[Mapping[str, pl.DataFrame]],
    history: Sequence[Mapping[str, pl.DataFrame]],
    match_ids: Mapping[str, uuid.UUID],
    comparison: pl.DataFrame,
    reference_kind: str,
) -> int:
    """Writes the session's priorities for the player's personal workspace; returns how many."""
    workspace = conn.execute(
        """
        SELECT w.id FROM workspace w JOIN app_user u ON u.id = w.created_by
        WHERE u.steam_id = %s AND w.kind = 'personal' AND u.deleted_at IS NULL
        """,
        (steam_id,),
    ).fetchone()
    if workspace is None:
        return 0
    tickrates = {str(t["match"]["match_id"][0]): float(t["match"]["tickrate"][0]) for t in session}
    found = prioritize(
        find(
            Dataset.from_matches(session),
            steam_id,
            comparison.select("metric", "basis", "session", "reference"),
            history=Dataset.from_matches(history),
        )
    )
    for priority, finding in enumerate(found, start=1):
        args = {
            "metric": finding.metric,
            "unit": REGISTRY[finding.metric].unit,
            "basis": finding.basis,
            "session": _clean(finding.session),
            "reference": _clean(finding.reference),
            "reference_kind": reference_kind,
            "events": finding.events,
            "rounds_touched": finding.rounds_touched,
            "rounds_lost": finding.rounds_lost,
            "actions": list(finding.actions),
            "indicator": finding.indicator,
            **{k: _clean(v) for k, v in finding.details.items()},
        }
        conn.execute(
            """
            INSERT INTO advice (steam_id, workspace_id, session_from, session_to, rule_id,
                                rule_version, priority, message_key, message_args, evidence,
                                session_id, cost, events, rounds_touched, rounds_lost)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                steam_id,
                workspace[0],
                span[0],
                span[1],
                finding.rule,
                finding.rule_version,
                priority,
                finding.message_key,
                Jsonb(args),
                Jsonb(
                    evidence_rows(finding, match_ids, tickrates),
                    dumps=lambda o: json.dumps(o, default=str),
                ),
                session_id,
                finding.cost,
                finding.events,
                finding.rounds_touched,
                finding.rounds_lost,
            ),
        )
    return len(found)
