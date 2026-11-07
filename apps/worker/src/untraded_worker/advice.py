# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""A session's findings (`advice`), computed right after its report by the `session` job.

The rules are those of `untraded.advice`: they compare the session with the reference the
report used (the player's own days, or their level) and look at the days before it for patterns.
Every finding is kept, with its evidence: the three priorities, then the others; each event gets
the tick to jump to in the demo, `LEAD` before it happened (`demo_gototick`).
"""

from __future__ import annotations

import datetime as dt
import json
import math
import uuid
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any

import polars as pl
import psycopg
from psycopg.types.json import Jsonb

from untraded.advice import PRIORITIES, Finding, find, split_findings
from untraded.metrics import REGISTRY, Dataset

MAX_EVIDENCE = 200
"""Events stored per finding, the first ones: far more than a real session holds, so that a crafted
demo cannot inflate a report. The finding's `events` keeps the true count."""
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
    for event in found.evidence.head(MAX_EVIDENCE).iter_rows(named=True):
        sha = event["match_id"]
        lead = int(LEAD.total_seconds() * tickrates.get(sha, 64.0))
        row = {k: _clean(v) for k, v in event.items() if k != "match_id"}
        row["match_id"] = str(match_ids[sha])
        row["goto_tick"] = max(0, int(event["tick"]) - lead)
        rows.append(row)
    return rows


def numbered(
    priorities: Sequence[Finding], others: Sequence[Finding]
) -> Iterator[tuple[int, Finding]]:
    """The value of `advice.priority` for each finding. The others always start past the
    priorities' range, even with fewer priorities than that (when the other findings all repeat
    their events): a number within it is what makes a priority for the readers."""
    yield from enumerate(priorities, start=1)
    yield from enumerate(others, start=PRIORITIES + 1)


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
    """Writes the session's findings for the player's personal workspace, the priorities and the
    others; returns how many rows it wrote."""
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
    priorities, others = split_findings(
        find(
            Dataset.from_matches(session),
            steam_id,
            comparison.select("metric", "basis", "session", "reference"),
            history=Dataset.from_matches(history),
            test_chance=reference_kind == "self",
        )
    )
    for priority, finding in numbered(priorities, others):
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
            "chance": _clean(finding.chance),
            "strong": finding.strong,
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
    return len(priorities) + len(others)


def votes_on_sessions_of(
    conn: psycopg.Connection[Any], steam_id: int, match_ids: Sequence[uuid.UUID]
) -> list[tuple[Any, ...]]:
    """The votes on the findings of the player's sessions holding these matches, oldest first."""
    return conn.execute(
        """
        SELECT f.user_id, f.vote, f.comment, f.created_at, a.rule_id, a.rule_version,
               a.message_args->>'map', a.message_args->>'side', a.message_args->>'zone'
        FROM advice_feedback f
        JOIN advice a ON a.id = f.advice_id
        JOIN play_session s ON s.id = a.session_id
        WHERE s.steam_id = %s AND EXISTS (
            SELECT 1 FROM play_session_match sm
            WHERE sm.session_id = s.id AND sm.match_id = ANY(%s)
        )
        ORDER BY f.created_at
        """,
        (steam_id, list(match_ids)),
    ).fetchall()


def restore_votes(
    conn: psycopg.Connection[Any], session_id: uuid.UUID, votes: Iterable[tuple[Any, ...]]
) -> None:
    """Puts the votes back on the same findings of a recomputed session.

    The same finding is the same rule at the same version, on the same spot for a pattern rule (the
    others have no spot): a vote judged that, and a new version is a new judgement to make. A
    finding that no longer fires takes its vote with it. When two sessions merge and both hold a
    vote by the same person on a finding, the latest stays: the votes come oldest first."""
    for user, vote, comment, voted_at, rule, version, map_, side, zone in votes:
        conn.execute(
            """
            INSERT INTO advice_feedback (advice_id, user_id, vote, comment, created_at)
            SELECT a.id, %s::uuid, %s::smallint, %s::text, %s::timestamptz
            FROM advice a
            WHERE a.session_id = %s AND a.rule_id = %s AND a.rule_version = %s
              AND a.message_args->>'map' IS NOT DISTINCT FROM %s::text
              AND a.message_args->>'side' IS NOT DISTINCT FROM %s::text
              AND a.message_args->>'zone' IS NOT DISTINCT FROM %s::text
            ON CONFLICT (advice_id, user_id) DO UPDATE
            SET vote = EXCLUDED.vote, comment = EXCLUDED.comment, created_at = EXCLUDED.created_at
            """,
            (user, vote, comment, voted_at, session_id, rule, version, map_, side, zone),
        )
