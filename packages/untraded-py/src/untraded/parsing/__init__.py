# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Demo parsing. The only package allowed to import demoparser2 (ADR 0002)."""

from untraded.parsing.header import DemoHeader, read_header

__all__ = ["DemoHeader", "read_header"]
