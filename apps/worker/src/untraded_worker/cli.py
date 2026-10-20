# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""`untraded-worker run`: process the job queue (UNTRADED_DATABASE_URL, UNTRADED_STORE_DIR)."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from untraded_worker import conninfo
from untraded_worker.jobs import HANDLERS
from untraded_worker.runner import Worker


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="untraded-worker", description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    run = actions.add_parser("run", help="process jobs until stopped")
    run.add_argument("--kinds", help="comma-separated job kinds (default: all)")
    run.add_argument("--once", action="store_true", help="stop when no job is ready")
    run.add_argument("--name", help="worker name recorded on its jobs (default: host name)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    kinds = args.kinds.split(",") if args.kinds else list(HANDLERS)
    unknown = set(kinds) - set(HANDLERS)
    if unknown:
        parser.error(f"unknown job kinds: {sorted(unknown)} (known: {sorted(HANDLERS)})")
    if not kinds:
        parser.error("no job handler is registered yet")
    worker = Worker(conninfo(), {k: HANDLERS[k] for k in kinds})
    if args.name:
        worker.name = args.name
    processed = worker.run(once=args.once)
    logging.info("stopped after %s job(s)", processed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
