# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Finding the codes in what a player pastes."""

from __future__ import annotations

from untraded_api.onboarding import AUTH_CODE, SHARE_CODE, find_code, place_codes

SHARE = "CSGO-a2b3c-D4E5F-g6h7j-K8L9M-n2p3q"


def test_a_share_code_is_found_in_cs2_s_link_or_with_spaces() -> None:
    assert find_code(SHARE_CODE, SHARE) == SHARE
    assert find_code(SHARE_CODE, f"  {SHARE}\n") == SHARE
    link = f"steam://rungame/730/76561202255233023/+csgo_download_match%20{SHARE}"
    assert find_code(SHARE_CODE, link) == SHARE
    assert find_code(SHARE_CODE, "CSGO-a2b3c-D4E5F") is None


def test_an_authentication_code_is_found_whatever_its_case_and_spaces() -> None:
    assert find_code(AUTH_CODE, "abcd-12345-efgh".upper()) == "ABCD-12345-EFGH"
    assert find_code(AUTH_CODE, " ABCD - 12345 - EFGH ") == "ABCD-12345-EFGH"
    assert find_code(AUTH_CODE, "ABCD-1234-EFGH") is None


def test_a_share_code_is_never_read_as_an_authentication_code() -> None:
    # Upper-cased, a share code holds a piece with the form of an authentication code.
    assert find_code(AUTH_CODE, SHARE.upper()) is None


def test_codes_given_the_other_way_round_are_put_back() -> None:
    assert place_codes("abcd-12345-efgh", SHARE) == ("ABCD-12345-EFGH", SHARE)
    assert place_codes(SHARE, "abcd-12345-efgh") == ("ABCD-12345-EFGH", SHARE)
    # One misplaced code alone is not guessed: the field it is in is reported.
    assert place_codes(SHARE, SHARE) == (None, SHARE)
    assert place_codes("ABCD-12345-EFGH", "ABCD-12345-EFGH") == ("ABCD-12345-EFGH", None)
