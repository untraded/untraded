# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Downloads a demo over HTTP, resuming interrupted transfers.

Valve replay servers throttle each connection (about 50 to 170 KB/s, spike S0.1) and drop it
every few MB, so the transfer resumes with `Range` requests and goes on while bytes arrive. The
`.part` file stays between attempts, and between jobs, so a retried job resumes too.
"""

from __future__ import annotations

import http.client
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CHUNK = 1 << 16
READ_TIMEOUT_S = 60.0
"""A connection that sends nothing for this long is dropped (and resumed)."""
MAX_TRIES_WITHOUT_PROGRESS = 5
RETRY_DELAY_S = 5.0
GONE = frozenset({404, 410})
"""Statuses meaning the demo no longer exists (Valve deletes demos after about 30 days)."""


class DownloadError(OSError):
    """The download failed for now; the job is retried later."""


class DemoGone(Exception):  # noqa: N818 (an outcome, not a failure)
    """The server says the demo does not exist (any more)."""

    def __init__(self, status: int) -> None:
        super().__init__(f"HTTP {status}")
        self.status = status


@dataclass(frozen=True)
class Downloaded:
    bytes: int
    tries: int
    resumed: bool


def check_url(url: str) -> None:
    """Only http(s) URLs are fetched."""
    if urllib.parse.urlsplit(url).scheme not in {"http", "https"}:
        raise ValueError(f"not an http(s) URL: {url!r}")


def fetch(url: str, target: Path, *, retry_delay_s: float = RETRY_DELAY_S) -> Downloaded:
    """Downloads `url` to `target` through `target.part`. Raises DemoGone or DownloadError."""
    check_url(url)
    partial = target.with_name(target.name + ".part")
    partial.parent.mkdir(parents=True, exist_ok=True)
    resumed = partial.exists() and partial.stat().st_size > 0
    tries = without_progress = 0
    while True:
        tries += 1
        have = partial.stat().st_size if partial.exists() else 0
        try:
            if _transfer(url, partial, have):
                break
            error = "short read"
        except DemoGone:
            raise
        except (OSError, http.client.HTTPException) as failure:  # URLError is an OSError
            error = str(failure)
        now = partial.stat().st_size if partial.exists() else 0
        without_progress = 0 if now > have else without_progress + 1
        if without_progress >= MAX_TRIES_WITHOUT_PROGRESS:
            raise DownloadError(f"{error} (at {now} bytes, after {tries} tries)")
        time.sleep(retry_delay_s)
    partial.replace(target)
    return Downloaded(bytes=target.stat().st_size, tries=tries, resumed=resumed)


def _transfer(url: str, partial: Path, have: int) -> bool:
    """One request; True when the file is complete."""
    request = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    try:
        response = urllib.request.urlopen(request, timeout=READ_TIMEOUT_S)
    except urllib.error.HTTPError as error:
        if error.code in GONE:
            raise DemoGone(error.code) from error
        if error.code == 416 and have:  # nothing left after `have`: already complete
            return True
        raise
    with response:
        # 206 continues the file; 200 means the server ignored Range: start over.
        append = response.status == 206
        expected = response.headers.get("Content-Length")
        total = (have if append else 0) + int(expected) if expected is not None else None
        with partial.open("ab" if append else "wb") as out:
            while chunk := response.read(CHUNK):
                out.write(chunk)
    return total is None or partial.stat().st_size == total
