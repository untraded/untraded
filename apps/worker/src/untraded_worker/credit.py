# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Whom a match counts for. A player listed in `match_player` is only someone a demo names, and
anyone can edit a demo before sending it: adding a Steam ID must not put a match on that player's
account. So a match counts for a player when:

- it came from a source that vouches for everyone in it: a demo Valve served to the collector
  (`valve_bot`), or the demo account's own import (an `upload` with a `demo:` id, which only
  `untraded-worker import-demo` writes: a sent demo's id is a UUID the API draws);
- or that player sent it themselves (whatever else it names, they answer for it).

Any other kind of source (a future URL or browser extension) counts for its sender only, until it
is added here on purpose. A refused upload counts for nobody, and neither does the upload of an
account since erased: its `source_id` is null.

What follows from it: their sessions, their reference, the match in their list. The other players
remain in the match, as non-registered players are, and see it if they send the same file: the
demo is known by its hash, so it merges (`jobs.ParseJob`), and it then counts for them too. Two
uploads of the same file confirm nothing for a third player: they could be two accounts of one
person."""

from __future__ import annotations


def credited(match: str, steam_id: str) -> str:
    """A SQL condition: the match counts for the player. `match` and `steam_id` are SQL expressions
    of the enclosing query (trusted constants, never input)."""
    return f"""EXISTS (
        SELECT 1 FROM match_source credit_ms
        LEFT JOIN ingest_source credit_s ON credit_s.id = credit_ms.source_id
        LEFT JOIN app_user credit_u ON credit_u.id = credit_s.user_id
        WHERE credit_ms.match_id = {match} AND credit_ms.rejected IS NULL
          AND (credit_ms.kind = 'valve_bot'
               OR (credit_ms.kind = 'upload' AND starts_with(credit_ms.external_id, 'demo:'))
               OR credit_u.steam_id = {steam_id}))"""
