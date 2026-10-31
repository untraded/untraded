# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The demo account: `untraded-worker import-demo <directory>` loads the matches that
`untraded demo build` wrote (anonymized canonical tables and `demo.json`) for a demo user, as
the parse job would: tables and metrics, round replays, SQL rows, access, then the sessions.

The demo user is created as an invited account signing in once (`open_auth_session`), so it has
a personal workspace like any player, and a consent to analysis only (never the research
corpus). It has no source: the collector never follows it. Running the import again skips the
matches already loaded (by their id, the `sha256` column)."""

from __future__ import annotations

import datetime as dt
import json
import logging
import secrets
import uuid
from pathlib import Path
from typing import Any

import psycopg

from untraded.parsing import CanonicalMatch
from untraded_worker import load, replays, sessions
from untraded_worker.analysis import analyze
from untraded_worker.store import LocalStore

log = logging.getLogger("untraded.worker")


def ensure_user(
    conn: psycopg.Connection[Any], steam_id: int, name: str, consent_version: str
) -> uuid.UUID:
    """The demo user, created on the first import, with its consent to analysis."""
    found = conn.execute(
        "SELECT id FROM app_user WHERE steam_id = %s AND deleted_at IS NULL", (steam_id,)
    ).fetchone()
    if found is None:
        conn.execute(
            "INSERT INTO invitation (steam_id, display_name) VALUES (%s, %s) "
            "ON CONFLICT (steam_id) DO UPDATE SET display_name = EXCLUDED.display_name, "
            "accepted_at = NULL",
            (steam_id, name),
        )
        # The first sign-in creates the user and its personal workspace; the session goes.
        token = secrets.token_bytes(32)
        row = conn.execute(
            "SELECT open_auth_session(%s, %s, interval '1 minute')", (steam_id, token)
        ).fetchone()
        if row is None or row[0] is None:
            raise RuntimeError("the demo user was erased: its row must go before a new import")
        conn.execute("DELETE FROM auth_session WHERE token_hash = %s", (token,))
        found = row
    user = uuid.UUID(str(found[0]))
    conn.execute(
        "INSERT INTO consent (user_id, text_version, analysis, research_corpus, recorded_by) "
        "SELECT %s, %s, true, false, 'demo import' WHERE NOT EXISTS ("
        "SELECT 1 FROM consent_current WHERE user_id = %s AND text_version = %s AND analysis)",
        (user, consent_version, user, consent_version),
    )
    return user


def import_match(
    conn: psycopg.Connection[Any], store: LocalStore, directory: Path, entry: dict[str, Any]
) -> uuid.UUID | None:
    """One match of the demo, in one transaction; None when it is already loaded."""
    canonical = CanonicalMatch.read(directory)
    if canonical.match_id != str(entry["match_id"]):
        raise ValueError(f"{directory}: its tables are not the match demo.json names")
    with conn.transaction():
        known = conn.execute(
            "SELECT id FROM match WHERE sha256 = %s", (canonical.match_id,)
        ).fetchone()
        if known is not None:
            return None
        played_at = dt.datetime.fromisoformat(str(entry["played_at"]))
        row = conn.execute(
            "INSERT INTO match (mode, status, played_at) VALUES (%s, 'parsing', %s) RETURNING id",
            (str(entry["mode"]), played_at),
        ).fetchone()
        assert row is not None
        match_id = uuid.UUID(str(row[0]))
        conn.execute(
            "INSERT INTO match_source (match_id, kind, external_id) VALUES (%s, 'upload', %s)",
            (match_id, f"demo:{canonical.match_id}"),
        )
        analysis = analyze(canonical.tables())
        prefix = f"matches/{match_id}"
        store.write_tables(prefix, analysis.tables)
        try:
            load.load_match(conn, match_id, analysis)
            conn.execute(
                "UPDATE match SET status = 'ready', parquet_prefix = %s, parsed_at = now() "
                "WHERE id = %s",
                (prefix, match_id),
            )
            load.refresh_access(conn, match_id)
            sessions.queue_sessions(conn, match_id)
        except Exception:
            store.delete_prefix(prefix)  # rolled back: no row will point at these files
            raise
    try:
        replays.write_replays(store, prefix, analysis.tables)
    except Exception:  # the viewer's files are derived: the analysis stands without them
        log.exception("replays of match %s failed; `untraded-worker replays` retries", match_id)
    return match_id


def import_demo(
    conn: psycopg.Connection[Any],
    store: LocalStore,
    root: Path,
    *,
    steam_id: int,
    name: str,
    consent_version: str,
) -> int:
    """Loads every match of `root/demo.json` not loaded yet; returns how many."""
    entries = json.loads((root / "demo.json").read_text(encoding="utf-8"))
    with conn.transaction():
        ensure_user(conn, steam_id, name, consent_version)
    done = 0
    for entry in entries:
        match_id = str(entry["match_id"])
        if not match_id.isalnum():
            raise ValueError(f"unexpected match id in demo.json: {match_id!r}")
        loaded = import_match(conn, store, root / "matches" / match_id, entry)
        if loaded is not None:
            log.info("demo match %s loaded as %s", match_id, loaded)
            done += 1
    # The demo replays real matches: it stays out of the references by level.
    conn.execute("UPDATE player SET benchmark_opt_out = true WHERE steam_id = %s", (steam_id,))
    return done
