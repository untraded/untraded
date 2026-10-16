# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Demo parsing. The only package allowed to import demoparser2 (ADR 0002)."""

from untraded.parsing.adapter import CanonicalMatch, UnsupportedModeError, parse_demo
from untraded.parsing.header import DemoHeader, read_header
from untraded.parsing.schema import MODES, SCHEMA_VERSION, CanonicalError

__all__ = [
    "MODES",
    "SCHEMA_VERSION",
    "CanonicalError",
    "CanonicalMatch",
    "DemoHeader",
    "UnsupportedModeError",
    "parse_demo",
    "read_header",
]
