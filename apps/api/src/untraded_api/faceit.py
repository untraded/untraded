# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""When a FACEIT match was played, from FACEIT's Data API.

A FACEIT demo downloaded from a match room is named after the match (`1-<uuid>-1-1.dem.zst`),
and the demo itself carries no date: the API asks FACEIT for the match's start, so the player
does not have to type it (the file's date is the download's, not the match's). Best effort:
without `FACEIT_API_KEY`, or when FACEIT does not answer, the date the player gave stays.

The calls are bounded: each answer (and each failure) is kept an hour, at most `CONCURRENT`
calls run at once (a request that finds none free gets no date rather than waiting), and a call
gives up after a few seconds. A player cannot make the server hammer FACEIT with its key.
"""

from __future__ import annotations

import datetime as dt
import re
import threading
import time

import httpx

MATCHES = "https://open.faceit.com/data/v4/matches/{}"
MATCH_ID = re.compile(r"1-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
TIMEOUT = httpx.Timeout(3.0, connect=2.0)
CONCURRENT = 4
KEEP = 3600.0
"""Seconds an answer is kept."""
CS2_RELEASE = dt.datetime(2023, 9, 27, tzinfo=dt.UTC)
"""No CS2 match started before it."""

_slots = threading.BoundedSemaphore(CONCURRENT)
_cache: dict[str, tuple[float, dt.datetime | None]] = {}
_cache_lock = threading.Lock()


def match_id(file_name: str) -> str | None:
    """The FACEIT match id a demo's file name holds, if any, in lower case."""
    found = MATCH_ID.search(file_name.lower())
    return found.group(0) if found else None


def plausible(when: dt.datetime | None, now: dt.datetime | None = None) -> dt.datetime | None:
    """`when` if a CS2 match can have started then (not before CS2, not tomorrow), else None."""
    limit = (now or dt.datetime.now(dt.UTC)) + dt.timedelta(days=1)
    return when if when is not None and CS2_RELEASE <= when <= limit else None


def _ask(client: httpx.Client, api_key: str, faceit_id: str) -> dt.datetime | None:
    try:
        response = client.get(
            MATCHES.format(faceit_id),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            return None
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    for key in ("started_at", "configured_at"):
        value = body.get(key) if isinstance(body, dict) else None
        if type(value) is int and value > 0:
            try:
                return plausible(dt.datetime.fromtimestamp(value, dt.UTC))
            except (OverflowError, OSError, ValueError):
                return None
    return None


def started_at(client: httpx.Client, api_key: str, faceit_id: str) -> dt.datetime | None:
    """The match's start (`started_at`, else `configured_at`), or None when FACEIT cannot say,
    is busy, or answered something no CS2 match could have."""
    if MATCH_ID.fullmatch(faceit_id) is None:
        return None
    now = time.monotonic()
    with _cache_lock:
        kept = _cache.get(faceit_id)
        if kept is not None and now - kept[0] < KEEP:
            return kept[1]
    if not _slots.acquire(blocking=False):
        return None  # too many calls already: no date rather than a queue of threads
    try:
        when = _ask(client, api_key, faceit_id)
    finally:
        _slots.release()
    with _cache_lock:
        if len(_cache) > 10_000:  # an old answer is cheap to ask again
            _cache.clear()
        _cache[faceit_id] = (now, when)
    return when


def forget() -> None:
    """Empties the kept answers (tests)."""
    with _cache_lock:
        _cache.clear()
