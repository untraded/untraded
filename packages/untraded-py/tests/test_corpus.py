# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
import bz2
import hashlib
import tomllib
from pathlib import Path

import pytest

from untraded import corpus
from untraded.cli import main
from untraded.corpus.manifest import CorpusDemo, Manifest, ManifestError, dumps
from untraded.demofile import DEMO_MAGIC
from untraded.parsing import DemoHeader

SHA = "a" * 64


def fake_header(_: Path) -> DemoHeader:
    return DemoHeader(map_name="de_nuke", game_build="14190", server_name="test")


def make_demo(path: Path, seed: int) -> bytes:
    content = DEMO_MAGIC + bytes([seed]) * 5000
    path.write_bytes(bz2.compress(content))
    return content


def demo(**overrides: object) -> CorpusDemo:
    fields: dict[str, object] = {
        "id": "faceit-2026-10-14-nuke-01",
        "source": "faceit",
        "map": "de_nuke",
        "sha256": SHA,
        "bytes": 332_000_000,
        "stored_as": ".dem.zst",
        "game_build": "14190",
    } | overrides
    return CorpusDemo(**fields)  # type: ignore[arg-type]


def test_manifest_round_trips(tmp_path: Path) -> None:
    manifest = Manifest(
        [
            demo(played_at="2026-10-14", notes='quote " backslash \\ accent é'),
            demo(id="scrim-undated-anubis-01", source="scrim", sha256="b" * 64, map="de_anubis"),
        ]
    )
    path = tmp_path / "manifest.toml"
    corpus.save(manifest, path)
    assert corpus.load(path) == manifest
    assert tomllib.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1


def test_missing_manifest_is_empty(tmp_path: Path) -> None:
    assert corpus.load(tmp_path / "none.toml").demos == []


def test_optional_fields_are_omitted() -> None:
    entry = dumps(Manifest([demo()])).split("[[demo]]")[1]
    assert "played_at" not in entry
    assert "notes" not in entry


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"source": "wingman"}, "source"),
        ({"sha256": "XYZ"}, "sha256"),
        ({"bytes": 0}, "bytes"),
        ({"played_at": "14/10/2026"}, "played_at"),
        ({"id": ""}, "empty"),
    ],
)
def test_invalid_entries_are_rejected(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ManifestError, match=message):
        demo(**overrides)


def test_duplicates_are_rejected() -> None:
    manifest = Manifest([demo()])
    with pytest.raises(ManifestError, match="duplicate id"):
        manifest.add(demo(sha256="b" * 64))
    with pytest.raises(ManifestError, match="same demo"):
        manifest.add(demo(id="other"))


def test_next_id_numbers_demos_of_the_same_day_and_map() -> None:
    manifest = Manifest([demo()])
    assert manifest.next_id("faceit", "2026-10-14", "de_nuke") == "faceit-2026-10-14-nuke-02"
    assert manifest.next_id("pro", None, "de_dust2") == "pro-undated-dust2-01"


def test_add_stores_the_demo_as_received_and_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "inbox" / "match.dem.bz2"
    source.parent.mkdir()
    content = make_demo(source, 1)
    manifest = Manifest()
    corpus_dir = tmp_path / "corpus"

    added = corpus.add(
        manifest, corpus_dir, source, source="faceit", played_at="2026-10-14",
        header_reader=fake_header,
    )  # fmt: skip

    assert added.new
    assert added.demo.sha256 == hashlib.sha256(content).hexdigest()
    assert added.demo.id == "faceit-2026-10-14-nuke-01"
    stored = corpus.stored_path(corpus_dir, added.demo)
    assert stored.name.endswith(".dem.bz2")
    assert stored.read_bytes() == source.read_bytes()
    again = corpus.add(manifest, corpus_dir, source, source="faceit", header_reader=fake_header)
    assert not again.new
    assert len(manifest.demos) == 1


def test_verify_detects_missing_and_corrupt_files(tmp_path: Path) -> None:
    source = tmp_path / "match.dem.bz2"
    make_demo(source, 2)
    manifest = Manifest()
    added = corpus.add(manifest, tmp_path, source, source="pro", header_reader=fake_header)
    stored = corpus.stored_path(tmp_path, added.demo)

    assert corpus.verify(added.demo, tmp_path) is corpus.Status.OK
    stored.write_bytes(stored.read_bytes()[:-20])
    assert corpus.verify(added.demo, tmp_path) is corpus.Status.CORRUPT
    assert corpus.verify(added.demo, tmp_path, full=False) is corpus.Status.OK
    stored.unlink()
    assert corpus.verify(added.demo, tmp_path) is corpus.Status.MISSING


def test_cli_verify_and_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "match.dem.bz2"
    make_demo(source, 3)
    manifest_path = tmp_path / "manifest.toml"
    manifest = Manifest()
    corpus.add(manifest, tmp_path, source, source="scrim", header_reader=fake_header)
    corpus.save(manifest, manifest_path)
    monkeypatch.setenv("UNTRADED_CORPUS_DIR", str(tmp_path))

    assert main(["corpus", "--manifest", str(manifest_path), "--dir", str(tmp_path), "list"]) == 0
    assert "scrim-undated-nuke-01" in capsys.readouterr().out
    verify = ["corpus", "--manifest", str(manifest_path), "--dir", str(tmp_path), "verify"]
    assert main(verify) == 0
    assert main([*verify, "unknown-id"]) == 2
    assert "unknown ids" in capsys.readouterr().err


def test_a_plain_demo_is_stored_compressed(tmp_path: Path) -> None:
    source = tmp_path / "match.dem"
    content = DEMO_MAGIC + bytes(50_000)
    source.write_bytes(content)
    manifest = Manifest()
    added = corpus.add(manifest, tmp_path / "c", source, source="pro", header_reader=fake_header)

    assert added.demo.stored_as == ".dem.zst"
    assert added.demo.sha256 == hashlib.sha256(content).hexdigest()
    stored = corpus.stored_path(tmp_path / "c", added.demo)
    assert stored.stat().st_size < len(content)
    assert corpus.verify(added.demo, tmp_path / "c") is corpus.Status.OK
