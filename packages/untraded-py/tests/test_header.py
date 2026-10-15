# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Reads a real demo header. Demos never go into git: set UNTRADED_TEST_DEMO to run it locally."""

import os
from pathlib import Path

import pytest

from untraded.parsing import read_header

DEMO = os.environ.get("UNTRADED_TEST_DEMO")


@pytest.mark.skipif(DEMO is None, reason="set UNTRADED_TEST_DEMO to a real demo file")
def test_reads_map_and_build_from_a_real_demo() -> None:
    header = read_header(Path(str(DEMO)))
    assert header.map_name.startswith("de_")
    assert header.game_build.isdigit()
