# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The validator of a round replay and how `If-None-Match` is compared, without a database
(the route itself is tested in `test_matches.py`)."""

from __future__ import annotations

from untraded_api.matches import none_match, replay_etag


def test_the_etag_is_strong_and_follows_the_bytes() -> None:
    etag = replay_etag(b"replay")
    assert etag == replay_etag(b"replay")
    assert etag.startswith('"')
    assert etag.endswith('"')
    assert not etag.startswith("W/")
    assert replay_etag(b"replay, rewritten") != etag


def test_if_none_match_is_a_weak_comparison() -> None:
    etag = replay_etag(b"replay")
    assert none_match(etag, etag)
    assert none_match(f"W/{etag}", etag)  # the web's relay weakens the tags it relays
    assert none_match(f'"other", {etag}', etag)
    assert none_match(f'"other",W/{etag}', etag)
    assert none_match("*", etag)
    assert not none_match(None, etag)
    assert not none_match("", etag)
    assert not none_match('"other"', etag)
    assert not none_match(etag.strip('"'), etag)  # unquoted is not the tag
