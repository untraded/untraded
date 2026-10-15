# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
import bz2
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from untraded import corpus
from untraded.corpus.manifest import Manifest
from untraded.corpus.sync import SftpRemote, SyncError, pull, push
from untraded.demofile import DEMO_MAGIC
from untraded.parsing import DemoHeader


class DirRemote:
    """A shared store backed by a local directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def names(self) -> set[str]:
        return {p.name for p in self.root.iterdir()}

    def upload(self, local: Path, name: str, *, resume: bool = False) -> None:
        self.resumed = getattr(self, "resumed", []) + ([name] if resume else [])
        shutil.copyfile(local, self.root / name)
        (self.root / f"{name}.part").unlink(missing_ok=True)

    def download(self, name: str, local: Path) -> None:
        shutil.copyfile(self.root / name, local)


def header(_: Path) -> DemoHeader:
    return DemoHeader(map_name="de_inferno", game_build="14190", server_name="")


def corpus_with_demos(tmp_path: Path, count: int) -> tuple[Manifest, Path]:
    manifest = Manifest()
    corpus_dir = tmp_path / "local"
    for seed in range(count):
        source = tmp_path / f"in{seed}.dem.bz2"
        source.write_bytes(bz2.compress(DEMO_MAGIC + bytes([seed]) * 4000))
        corpus.add(manifest, corpus_dir, source, source="scrim", header_reader=header)
    return manifest, corpus_dir


def test_push_uploads_only_what_the_store_lacks(tmp_path: Path) -> None:
    manifest, corpus_dir = corpus_with_demos(tmp_path, 2)
    remote = DirRemote(tmp_path / "store")
    remote.upload(corpus.stored_path(corpus_dir, manifest.demos[0]), manifest.demos[0].filename)

    report = push(manifest, corpus_dir, remote)

    assert [d.id for d in report.done] == [manifest.demos[1].id]
    assert remote.names() == {d.filename for d in manifest.demos}


def test_push_resumes_a_partial_upload(tmp_path: Path) -> None:
    manifest, corpus_dir = corpus_with_demos(tmp_path, 2)
    remote = DirRemote(tmp_path / "store")
    (remote.root / f"{manifest.demos[1].filename}.part").write_bytes(b"first bytes")

    push(manifest, corpus_dir, remote)

    assert remote.resumed == [manifest.demos[1].filename]
    assert remote.names() == {d.filename for d in manifest.demos}


def test_push_skips_a_corrupt_local_file(tmp_path: Path) -> None:
    manifest, corpus_dir = corpus_with_demos(tmp_path, 1)
    stored = corpus.stored_path(corpus_dir, manifest.demos[0])
    stored.write_bytes(stored.read_bytes()[:-10])

    report = push(manifest, corpus_dir, DirRemote(tmp_path / "store"))

    assert report.done == []
    assert report.skipped[0][1] == "local file corrupt"


def test_pull_restores_missing_demos_and_checks_them(tmp_path: Path) -> None:
    manifest, corpus_dir = corpus_with_demos(tmp_path, 3)
    remote = DirRemote(tmp_path / "store")
    push(manifest, corpus_dir, remote)
    for demo in manifest.demos[:2]:
        corpus.stored_path(corpus_dir, demo).unlink()
    damaged = manifest.demos[1].filename
    (remote.root / damaged).write_bytes(b"garbage")

    report = pull(manifest, corpus_dir, remote)

    assert [d.id for d in report.done] == [manifest.demos[0].id]
    assert report.skipped == [(manifest.demos[1], "downloaded file corrupt")]
    assert not corpus.stored_path(corpus_dir, manifest.demos[1]).exists()
    assert corpus.verify(manifest.demos[0], corpus_dir) is corpus.Status.OK


def test_dry_run_transfers_nothing(tmp_path: Path) -> None:
    manifest, corpus_dir = corpus_with_demos(tmp_path, 1)
    remote = DirRemote(tmp_path / "store")
    assert len(push(manifest, corpus_dir, remote, dry_run=True).done) == 1
    assert remote.names() == set()


@pytest.mark.parametrize("spec", ["nohost", ":path", "host:", ""])
def test_remote_spec_must_be_host_and_path(spec: str) -> None:
    with pytest.raises(SyncError, match="host:path"):
        SftpRemote.parse(spec)


def test_sftp_batches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"args": args, "input": kwargs["input"]})
        out = 'sftp> -ls -1 "corpus/demos"\ncorpus/demos/abc.dem.zst\ncorpus/demos/x.part\n'
        return subprocess.CompletedProcess(args, 0, stdout=out, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/sftp")
    remote = SftpRemote.parse("untraded-corpus:corpus/demos/")

    assert remote.names() == {"abc.dem.zst", "x.part"}
    remote.upload(tmp_path / "abc.dem.zst", "abc.dem.zst")
    remote.upload(tmp_path / "abc.dem.zst", "abc.dem.zst", resume=True)

    assert calls[0]["args"][-1] == "untraded-corpus"
    assert "BatchMode=yes" in calls[0]["args"]
    upload = calls[1]["input"].splitlines()
    assert upload[:2] == ['-mkdir "corpus"', '-mkdir "corpus/demos"']
    assert upload[-1] == 'rename "corpus/demos/abc.dem.zst.part" "corpus/demos/abc.dem.zst"'
    assert upload[-2].startswith("put ")
    assert calls[2]["input"].splitlines()[-2].startswith("reput ")


def test_sftp_failure_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_run(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 255, stdout="", stderr="Permission denied ().\n")

    monkeypatch.setattr(subprocess, "run", failing_run)
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/sftp")
    with pytest.raises(SyncError, match="Permission denied"):
        SftpRemote.parse("box:corpus").names()
