# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Sync the local corpus with the private shared store (ADR 0010).

The store is reached with the OpenSSH `sftp` client, available on Linux, macOS and Windows, so no
credential ever goes through this code: access is configured in `~/.ssh/config` (a host alias
with its key). The remote is written `host:path`, e.g. `untraded-corpus:corpus/demos`.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Protocol

from untraded.corpus.manifest import CorpusDemo, Manifest
from untraded.corpus.store import Status, stored_path, verify


class SyncError(RuntimeError):
    """The shared store could not be reached or a transfer failed."""


class Remote(Protocol):
    def names(self) -> set[str]:
        """File names present in the remote directory."""
        ...

    def upload(self, local: Path, name: str) -> None: ...

    def download(self, name: str, local: Path) -> None: ...


@dataclass(frozen=True)
class SftpRemote:
    host: str
    path: str

    @classmethod
    def parse(cls, spec: str) -> SftpRemote:
        host, sep, path = spec.partition(":")
        if not sep or not host or not path:
            raise SyncError(
                f"remote {spec!r}: expected host:path, e.g. untraded-corpus:corpus/demos"
            )
        return cls(host, path.rstrip("/"))

    def names(self) -> set[str]:
        # `-` ignores the error when the directory does not exist yet: the store is then empty.
        output = self._run([f"-ls -1 {_quote(self.path)}"])
        return {
            PurePosixPath(line).name for line in output if line and not line.startswith("sftp>")
        }

    def upload(self, local: Path, name: str) -> None:
        remote = f"{self.path}/{name}"
        partial = f"{remote}.part"
        commands = [f"-mkdir {_quote(parent)}" for parent in _parents(self.path)]
        commands += [
            f"-rm {_quote(partial)}",
            f"put {_quote(local.as_posix())} {_quote(partial)}",
            f"rename {_quote(partial)} {_quote(remote)}",
        ]
        self._run(commands)

    def download(self, name: str, local: Path) -> None:
        self._run([f"get {_quote(f'{self.path}/{name}')} {_quote(local.as_posix())}"])

    def _run(self, commands: Iterable[str]) -> list[str]:
        if shutil.which("sftp") is None:
            raise SyncError("the OpenSSH `sftp` client is not installed")
        batch = "\n".join(commands) + "\n"
        result = subprocess.run(
            ["sftp", "-q", "-o", "BatchMode=yes", "-b", "-", self.host],
            input=batch,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            raise SyncError(f"sftp {self.host}: {detail[-1] if detail else 'failed'}")
        return result.stdout.splitlines()


@dataclass
class SyncReport:
    done: list[CorpusDemo] = field(default_factory=list)
    skipped: list[tuple[CorpusDemo, str]] = field(default_factory=list)
    """Demos that could not be transferred, with the reason."""


def push(
    manifest: Manifest, corpus_dir: Path, remote: Remote, *, dry_run: bool = False
) -> SyncReport:
    """Uploads the manifest's demos that the store lacks. Each file is re-hashed first."""
    present = remote.names()
    report = SyncReport()
    for demo in manifest.demos:
        if demo.filename in present:
            continue
        status = verify(demo, corpus_dir)
        if status is not Status.OK:
            report.skipped.append((demo, f"local file {status.value}"))
            continue
        if not dry_run:
            remote.upload(stored_path(corpus_dir, demo), demo.filename)
        report.done.append(demo)
    return report


def pull(
    manifest: Manifest, corpus_dir: Path, remote: Remote, *, dry_run: bool = False
) -> SyncReport:
    """Downloads the manifest's demos missing locally, and checks each one before keeping it."""
    present = remote.names()
    report = SyncReport()
    for demo in manifest.demos:
        target = stored_path(corpus_dir, demo)
        if target.exists():
            continue
        if demo.filename not in present:
            report.skipped.append((demo, "not in the shared store"))
            continue
        if dry_run:
            report.done.append(demo)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        remote.download(demo.filename, partial)
        partial.replace(target)
        if (status := verify(demo, corpus_dir)) is not Status.OK:
            target.unlink()
            report.skipped.append((demo, f"downloaded file {status.value}"))
            continue
        report.done.append(demo)
    return report


def _quote(value: str) -> str:
    if '"' in value or "\n" in value:
        raise SyncError(f"unsupported path {value!r}")
    return f'"{value}"'


def _parents(path: str) -> list[str]:
    """`a/b/c` -> [`a`, `a/b`, `a/b/c`]: sftp's mkdir is not recursive."""
    parts = PurePosixPath(path).parts
    return [str(PurePosixPath(*parts[: i + 1])) for i in range(len(parts))]
