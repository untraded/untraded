# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""`untraded-worker run`: process the job queue (UNTRADED_DATABASE_URL, UNTRADED_STORE_DIR,
UNTRADED_UPLOADS_DIR, UNTRADED_UPLOAD_MAX_DEMO_GB, UNTRADED_DEMO_RETENTION_DAYS).
`untraded-worker replays`: write the 2D viewer's round replays of the matches parsed before.
`untraded-worker swings`: write the `swing` table of the matches parsed before.
`untraded-worker reanalyze`: analyse the matches parsed before again (new metrics or versions).
`untraded-worker backfill-spread`: fill the spread of the references of the sessions written
before it existed, without recomputing any session (none changes its id).
`untraded-worker backfill-team-stats`: write the team metrics of the matches parsed before them,
without recomputing anything else.
`untraded-worker retry-failed`: put the failed matches back in the queue, after a fix.
`untraded-worker refresh-access`: recompute which workspaces see every match (teams).
`untraded-worker import-demo <dir> [--team <dir>]`: load the demo account (`untraded demo build`)
and its team (`untraded demo team`).
`untraded-worker remove-demo-team`: delete the demo's team and erase its invented members."""

from __future__ import annotations

import argparse
import datetime as dt
import logging
from collections.abc import Sequence
from pathlib import Path

import psycopg

from untraded.demo import PROTAGONIST
from untraded.demo_team import TEAM_SLUG
from untraded_worker import (
    conninfo,
    demo,
    demo_team,
    isolated,
    levels,
    reanalyze,
    replays,
    retention,
    retry,
    spread,
    store_dir,
    swings,
    team_access,
    team_stats,
    uploads_dir,
)
from untraded_worker.jobs import dead_handlers, handlers
from untraded_worker.runner import Periodic, Worker
from untraded_worker.store import LocalStore

RETENTION_EVERY = dt.timedelta(minutes=10)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="untraded-worker", description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    run = actions.add_parser("run", help="process jobs until stopped")
    run.add_argument("--kinds", help="comma-separated job kinds (default: all)")
    run.add_argument("--once", action="store_true", help="stop when no job is ready")
    run.add_argument(
        "--name",
        help="worker name recorded on its jobs, unique per worker: a worker that starts takes back "
        "the jobs left running under its name (default: host name)",
    )
    again = actions.add_parser("replays", help="write the round replays of parsed matches")
    again.add_argument("--force", action="store_true", help="rewrite existing replays too")
    swing = actions.add_parser("swings", help="write the swing table of parsed matches")
    swing.add_argument("--force", action="store_true", help="rewrite existing swing tables too")
    again_all = actions.add_parser("reanalyze", help="analyse the matches parsed before again")
    again_all.add_argument("--force", action="store_true", help="every match, not only stale ones")
    actions.add_parser(
        "backfill-spread",
        help="fill reference_p10 and reference_p90 of existing sessions (nothing else changes)",
    )
    actions.add_parser(
        "backfill-team-stats",
        help="write the team metrics of matches parsed before them (nothing else changes)",
    )
    actions.add_parser("retry-failed", help="put the failed matches back in the queue")
    actions.add_parser(
        "refresh-access", help="recompute which workspaces see every match (rosters, sharing)"
    )
    demo_parser = actions.add_parser("import-demo", help="load the demo account's matches")
    demo_parser.add_argument("directory", type=Path, help="written by `untraded demo build`")
    demo_parser.add_argument("--name", default="Demo")
    demo_parser.add_argument("--consent-version", default="2", help="the site's consent text")
    demo_parser.add_argument(
        "--team", type=Path, help="and the demo's team (written by `untraded demo team`)"
    )
    actions.add_parser(
        "remove-demo-team", help="delete the demo's team and erase its invented members"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    store = LocalStore(Path(store_dir()))
    if args.action == "replays":
        with psycopg.connect(conninfo(), autocommit=True) as conn:
            done = replays.backfill(conn, store, force=args.force)
        logging.info("replays written for %s match(es)", done)
        return 0
    if args.action == "reanalyze":
        with psycopg.connect(conninfo(), autocommit=True) as conn:
            done = reanalyze.backfill(conn, store, force=args.force)
        logging.info("%s match(es) analysed again", done)
        return 0
    if args.action == "backfill-spread":
        with psycopg.connect(conninfo(), autocommit=True) as conn:
            done = spread.backfill(conn, store)
        logging.info("spread filled for %s session(s)", done)
        return 0
    if args.action == "backfill-team-stats":
        with psycopg.connect(conninfo(), autocommit=True) as conn:
            done = team_stats.backfill(conn, store)
        logging.info("team metrics written for %s match(es)", done)
        return 0
    if args.action == "retry-failed":
        with psycopg.connect(conninfo(), autocommit=True) as conn:
            retried = retry.retry_failed(conn)
        logging.info("%s failed match(es) put back in the queue", retried.queued)
        return 0
    if args.action == "refresh-access":
        with psycopg.connect(conninfo(), autocommit=True) as conn:
            done = team_access.refresh_all(conn)
        logging.info("access to %s match(es) recomputed", done)
        return 0
    if args.action == "import-demo":
        with psycopg.connect(conninfo(), autocommit=True) as conn:
            done = demo.import_demo(
                conn,
                store,
                args.directory,
                steam_id=PROTAGONIST,
                name=args.name,
                consent_version=args.consent_version,
            )
            logging.info("%s demo match(es) loaded", done)
            if args.team is not None:
                done = demo_team.import_demo_team(
                    conn,
                    store,
                    args.team,
                    owner_steam_id=PROTAGONIST,
                    consent_version=args.consent_version,
                )
                logging.info("%s demo team match(es) loaded", done)
        return 0
    if args.action == "remove-demo-team":
        with psycopg.connect(conninfo(), autocommit=True) as conn:
            done = demo_team.remove_demo_team(conn, owner_steam_id=PROTAGONIST, slug=TEAM_SLUG)
        logging.info("demo team deleted, %s member(s) to erase", done)
        return 0
    if args.action == "swings":
        with psycopg.connect(conninfo(), autocommit=True) as conn:
            done = swings.backfill(conn, store, force=args.force)
        logging.info("swing tables written for %s match(es)", done)
        return 0
    uploads = Path(uploads_dir())
    known = handlers(store, uploads)
    kinds = args.kinds.split(",") if args.kinds else list(known)
    unknown = set(kinds) - set(known)
    if unknown:
        parser.error(f"unknown job kinds: {sorted(unknown)} (known: {sorted(known)})")
    keep = retention.configured()
    periodic = [
        Periodic(levels.EVERY, levels.compute_levels),
        Periodic(RETENTION_EVERY, retention.purge_sessions),
    ]
    if keep is not None:
        periodic.append(Periodic(RETENTION_EVERY, retention.Sweep(store, keep)))
    worker = Worker(
        conninfo(), {k: known[k] for k in kinds}, on_dead=dead_handlers(uploads), periodic=periodic
    )
    if args.name:
        worker.name = args.name
    if isolated.sweep_leftovers():
        logging.info("temporary files of interrupted parses deleted")
    processed = worker.run(once=args.once)
    logging.info("stopped after %s job(s)", processed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
