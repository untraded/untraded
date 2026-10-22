# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""`untraded-worker run`: process the job queue (UNTRADED_DATABASE_URL, UNTRADED_STORE_DIR,
UNTRADED_DEMO_RETENTION_DAYS). `untraded-worker replays`: write the 2D viewer's round replays of
the matches parsed before."""

from __future__ import annotations

import argparse
import datetime as dt
import logging
from collections.abc import Sequence
from pathlib import Path

import psycopg

from untraded_worker import conninfo, levels, replays, retention, store_dir
from untraded_worker.jobs import ON_DEAD, handlers
from untraded_worker.runner import Periodic, Worker
from untraded_worker.store import LocalStore

RETENTION_EVERY = dt.timedelta(minutes=10)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="untraded-worker", description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    run = actions.add_parser("run", help="process jobs until stopped")
    run.add_argument("--kinds", help="comma-separated job kinds (default: all)")
    run.add_argument("--once", action="store_true", help="stop when no job is ready")
    run.add_argument("--name", help="worker name recorded on its jobs (default: host name)")
    again = actions.add_parser("replays", help="write the round replays of parsed matches")
    again.add_argument("--force", action="store_true", help="rewrite existing replays too")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    store = LocalStore(Path(store_dir()))
    if args.action == "replays":
        with psycopg.connect(conninfo(), autocommit=True) as conn:
            done = replays.backfill(conn, store, force=args.force)
        logging.info("replays written for %s match(es)", done)
        return 0
    known = handlers(store)
    kinds = args.kinds.split(",") if args.kinds else list(known)
    unknown = set(kinds) - set(known)
    if unknown:
        parser.error(f"unknown job kinds: {sorted(unknown)} (known: {sorted(known)})")
    keep = retention.configured()
    periodic = [Periodic(levels.EVERY, levels.compute_levels)]
    if keep is not None:
        periodic.append(Periodic(RETENTION_EVERY, retention.Sweep(store, keep)))
    worker = Worker(conninfo(), {k: known[k] for k in kinds}, on_dead=ON_DEAD, periodic=periodic)
    if args.name:
        worker.name = args.name
    processed = worker.run(once=args.once)
    logging.info("stopped after %s job(s)", processed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
