# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The parse in a child process: its tables come back, and a stuck, dying or failing parser
fails the job instead of stopping the worker."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest

from untraded import fixtures
from untraded.parsing import CanonicalMatch, UnsupportedModeError
from untraded_worker.isolated import (
    PREFIX,
    IsolatedParse,
    ParseError,
    ParseTimeoutError,
    configured_timeout,
    sweep_leftovers,
)

FIXTURE = Path(__file__).parents[3] / "packages/untraded-py/tests/fixtures/premier-half"


# Module-level: the child process imports them by name.
def fixture_parse(path: Path, **_: Any) -> CanonicalMatch:
    return CanonicalMatch(**fixtures.read(FIXTURE))


def stuck_parse(path: Path, **_: Any) -> CanonicalMatch:
    time.sleep(60)
    raise AssertionError("not stopped")


def dying_parse(path: Path, **_: Any) -> CanonicalMatch:
    # A decompressed demo on its way, then killed, as the kernel's out-of-memory kill would.
    (Path(tempfile.mkdtemp()) / "big.dem").write_bytes(b"x" * 1000)
    os._exit(137)


def wrong_mode(path: Path, **_: Any) -> CanonicalMatch:
    raise UnsupportedModeError("mode 'wingman' is not analysed")


def broken_parse(path: Path, **_: Any) -> CanonicalMatch:
    raise ValueError("corrupt demo")


def test_the_tables_come_back(tmp_path: Path) -> None:
    parsed = IsolatedParse(fixture_parse, timeout=120)(tmp_path / "a.dem", mode="premier")
    expected = CanonicalMatch(**fixtures.read(FIXTURE))
    assert parsed.match_id == expected.match_id
    for name, table in expected.tables().items():
        assert parsed.tables()[name].equals(table), name


def test_a_stuck_parse_is_stopped(tmp_path: Path) -> None:
    started = time.monotonic()
    with pytest.raises(ParseTimeoutError, match="took over"):
        IsolatedParse(stuck_parse, timeout=3)(tmp_path / "a.dem")
    assert time.monotonic() - started < 30


def test_a_dead_or_failing_parser_fails_the_job(tmp_path: Path) -> None:
    with pytest.raises(ParseError, match="died"):
        IsolatedParse(dying_parse, timeout=60)(tmp_path / "a.dem")
    with pytest.raises(ParseError, match="corrupt demo"):
        IsolatedParse(broken_parse, timeout=60)(tmp_path / "a.dem")
    with pytest.raises(UnsupportedModeError, match="wingman"):
        IsolatedParse(wrong_mode, timeout=60)(tmp_path / "a.dem")


def test_the_timeout_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UNTRADED_PARSE_TIMEOUT_SECONDS", raising=False)
    assert configured_timeout() == 600
    monkeypatch.setenv("UNTRADED_PARSE_TIMEOUT_SECONDS", "90")
    assert configured_timeout() == 90
    monkeypatch.setenv("UNTRADED_PARSE_TIMEOUT_SECONDS", "0")
    with pytest.raises(ValueError, match="> 0"):
        configured_timeout()


def test_a_killed_parse_leaves_nothing_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    with pytest.raises(ParseError, match="died"):
        IsolatedParse(dying_parse, timeout=60)(tmp_path / "a.dem")
    assert list(tmp_path.iterdir()) == []  # the child's files were under the parse's directory
    (tmp_path / f"{PREFIX}left").mkdir()  # one that died with its worker
    assert sweep_leftovers() == 1
    assert list(tmp_path.iterdir()) == []
