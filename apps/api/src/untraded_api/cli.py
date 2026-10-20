# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""`untraded-api`: serves the API (UNTRADED_DATABASE_URL, UNTRADED_PUBLIC_URL, UNTRADED_WEB_URL)."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import uvicorn

from untraded_api.app import create_app
from untraded_api.settings import Settings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="untraded-api", description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    # Behind a reverse proxy (Caddy): trust its X-Forwarded-* headers.
    uvicorn.run(
        create_app(Settings.from_env()),
        host=args.host,
        port=args.port,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
