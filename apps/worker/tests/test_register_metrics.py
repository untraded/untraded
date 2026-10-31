# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The registry of metrics in PostgreSQL: written after an update, left alone otherwise, so two
transactions that load matches at once never wait on its rows."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

from untraded.metrics import REGISTRY
from untraded_worker.load import register_metrics

pytestmark = pytest.mark.db


@pytest.fixture
def db(conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    conn.execute(
        "TRUNCATE match, player, app_user, workspace, metric_definition, metric_current CASCADE"
    )
    return conn


def _versions(conn: psycopg.Connection[Any]) -> dict[str, tuple[str, str]]:
    """Each metric's current version and the row version (`xmin`) of its definition."""
    rows = conn.execute(
        "SELECT d.metric_id, d.version, d.xmin::text "
        "FROM metric_current c JOIN metric_definition d USING (metric_id, version)"
    ).fetchall()
    return {metric_id: (version, xmin) for metric_id, version, xmin in rows}


def test_the_registry_is_written_once(db: psycopg.Connection[Any]) -> None:
    register_metrics(db)
    first = _versions(db)
    assert {m: v for m, (v, _) in first.items()} == {m.id: m.version for m in REGISTRY.values()}
    register_metrics(db)
    assert _versions(db) == first  # the same rows: nothing was rewritten


def test_a_changed_definition_is_written_again(db: psycopg.Connection[Any]) -> None:
    register_metrics(db)
    db.execute("UPDATE metric_definition SET better = 'neutral', signed = NOT signed")
    register_metrics(db)
    rows = {
        r[0]: (r[1], r[2])
        for r in db.execute("SELECT metric_id, better, signed FROM metric_definition")
    }
    assert rows == {m.id: (m.better, m.signed) for m in REGISTRY.values()}


def test_two_loads_at_once_do_not_wait_on_the_registry(
    db: psycopg.Connection[Any], conninfo: str
) -> None:
    register_metrics(db)
    with (
        psycopg.connect(conninfo) as first,
        psycopg.connect(conninfo) as second,
    ):
        register_metrics(first)  # its transaction stays open, as a long match load's does
        second.execute("SET lock_timeout = '1s'")
        register_metrics(second)  # waited on `first` until its end, and could deadlock
        second.rollback()
        first.rollback()
