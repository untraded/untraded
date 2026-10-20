# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""`untraded-db`: apply, inspect and write migrations (Alembic, configured in code)."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from alembic import command
from alembic.config import Config

from untraded_db import MIGRATIONS, database_url


def config(url: str | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    cfg.set_main_option("sqlalchemy.url", url or database_url())
    return cfg


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="untraded-db", description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    upgrade = actions.add_parser("upgrade", help="apply migrations (default: all)")
    upgrade.add_argument("revision", nargs="?", default="head")
    actions.add_parser("current", help="show the revision of the database")
    actions.add_parser("history", help="list the migrations")
    revision = actions.add_parser("revision", help="write a new empty migration")
    revision.add_argument("-m", "--message", required=True)
    args = parser.parse_args(argv)

    cfg = config()
    if args.action == "upgrade":
        command.upgrade(cfg, args.revision)
    elif args.action == "current":
        command.current(cfg, verbose=True)
    elif args.action == "history":
        command.history(cfg)
    else:
        command.revision(cfg, message=args.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
