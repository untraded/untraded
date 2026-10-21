# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The secret format the collector reads (`apps/collector/src/secrets.ts`)."""

from __future__ import annotations

import base64

import pytest
from cryptography.exceptions import InvalidTag

from untraded_api.secrets_box import decrypt, encrypt, secret_key

KEY = bytes(range(32))


def test_a_secret_round_trips_and_stays_bound_to_its_row() -> None:
    sealed = encrypt(KEY, "AAAA-BBBBB-CCCC", "source-1")
    assert sealed[0] == 1
    assert len(sealed) == 1 + 12 + len("AAAA-BBBBB-CCCC") + 16
    assert b"AAAA" not in sealed
    assert decrypt(KEY, sealed, "source-1") == "AAAA-BBBBB-CCCC"
    with pytest.raises(InvalidTag):
        decrypt(KEY, sealed, "source-2")  # copied onto another row


def test_the_key_is_32_bytes_of_base64() -> None:
    assert secret_key(base64.b64encode(KEY).decode()) == KEY
    # Read like the collector does: without its padding, with spaces around, URL-safe.
    assert secret_key(base64.b64encode(KEY).decode().rstrip("=")) == KEY
    assert secret_key(" " + base64.b64encode(KEY).decode() + "\n") == KEY
    assert secret_key(base64.urlsafe_b64encode(KEY).decode()) == KEY
    for bad in ("", "not base64!", base64.b64encode(b"short").decode()):
        with pytest.raises(ValueError, match="UNTRADED_SECRET_KEY"):
            secret_key(bad)
