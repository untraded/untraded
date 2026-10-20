# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""`untraded parse` on several demos: dates from a manifest, failures reported, others kept."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from untraded import cli, fixtures
from untraded.demofile import CorruptDemoError
from untraded.parsing import CanonicalMatch

FIXTURE = Path(__file__).parent / "fixtures" / "premier-half"
SHA = "ab" * 32


def fake_parse(path: Path, **kwargs: Any) -> CanonicalMatch:
    """The `premier-half` fixture, with the demo's file stem as match id."""
    if path.stem == "broken":
        raise CorruptDemoError("not a demo")
    tables = fixtures.read(FIXTURE)
    tables["match"] = tables["match"].with_columns(
        pl.lit(path.stem).alias("match_id"),
        pl.lit(kwargs.get("played_at"), pl.Date).alias("played_at"),
    )
    return CanonicalMatch(**tables)


def run(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> int:
    monkeypatch.setattr(cli, "parse_demo", fake_parse)
    return cli.main(["parse", "--mode", "premier", "--jobs", "1", *argv])


def test_dates_come_from_the_manifest_by_sha256(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = tmp_path / "manifest.toml"
    manifest.write_text(
        "schema_version = 1\n\n[[demo]]\n"
        f'id = "valve-premier-2026-10-11-cache-01"\nsource = "valve-premier"\nmap = "de_cache"\n'
        f'played_at = "2026-10-11"\nsha256 = "{SHA}"\nbytes = 1\nstored_as = ".dem"\n'
        'game_build = "14190"\n',
        encoding="utf-8",
    )
    demos = [str(tmp_path / f"{SHA}.dem"), str(tmp_path / "unknown.dem")]
    out = tmp_path / "out"
    assert run(monkeypatch, [*demos, "--dates-from", str(manifest), "--out", str(out)]) == 0
    known = CanonicalMatch.read(out / "matches" / SHA)
    assert known.match["played_at"][0] == dt.date(2026, 10, 11)
    assert CanonicalMatch.read(out / "matches" / "unknown").match["played_at"][0] is None


def test_a_failed_demo_does_not_stop_the_others(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    demos = [str(tmp_path / "first.dem"), str(tmp_path / "broken.dem"), str(tmp_path / "last.dem")]
    assert run(monkeypatch, [*demos, "--out", str(tmp_path)]) == 1
    assert sorted(p.name for p in (tmp_path / "matches").iterdir()) == ["first", "last"]
    output = capsys.readouterr()
    assert "broken.dem: FAILED" in output.out
    assert "1 of 3 demo(s) failed" in output.err


def test_played_at_needs_a_single_demo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    argv = ["a.dem", "b.dem", "--played-at", "2026-10-10", "--out", str(tmp_path)]
    assert run(monkeypatch, argv) == 2
