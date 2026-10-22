# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The 2D viewer's round replays (`untraded.replay`), kept next to each match's tables:
`matches/{match_id}/replay/{round}.json.gz`. The parse job writes them; `untraded-worker replays`
writes them for matches parsed before, or again after a format change (`--force`)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import polars as pl
import psycopg

from untraded.replay import build_replays, to_json_gz
from untraded_worker.store import LocalStore

log = logging.getLogger("untraded.worker")


def replay_key(prefix: str, round_number: int) -> str:
    return f"{prefix}/replay/{round_number}.json.gz"


def write_replays(store: LocalStore, prefix: str, tables: Mapping[str, pl.DataFrame]) -> int:
    """Writes every round's replay; returns how many."""
    replays = build_replays(tables)
    for number, replay in replays.items():
        store.write_bytes(replay_key(prefix, number), to_json_gz(replay))
    return len(replays)


def backfill(conn: psycopg.Connection[Any], store: LocalStore, *, force: bool = False) -> int:
    """Writes the replays of the ready matches that have none (all of them with `force`);
    returns how many matches got replays. A match that fails is logged and skipped."""
    done = 0
    rows = conn.execute(
        "SELECT id, parquet_prefix FROM match WHERE status = 'ready' "
        "AND parquet_prefix IS NOT NULL ORDER BY parsed_at"
    ).fetchall()
    for match_id, prefix in rows:
        if not force and store.path(f"{prefix}/replay").is_dir():
            continue
        try:
            count = write_replays(store, prefix, store.read_tables(prefix))
        except Exception:  # one broken match must not stop the others
            log.exception("replays of match %s failed", match_id)
            continue
        log.info("match %s: %d round replay(s)", match_id, count)
        done += 1
    return done
