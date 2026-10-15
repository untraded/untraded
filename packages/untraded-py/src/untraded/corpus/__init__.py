# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Reference demo corpus: manifest and local store (ADR 0010)."""

from untraded.corpus.manifest import SOURCES, CorpusDemo, Manifest, ManifestError, load, save
from untraded.corpus.store import Added, Status, add, stored_path, verify

__all__ = [
    "SOURCES",
    "Added",
    "CorpusDemo",
    "Manifest",
    "ManifestError",
    "Status",
    "add",
    "load",
    "save",
    "stored_path",
    "verify",
]
