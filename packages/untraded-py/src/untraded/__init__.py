# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Untraded: open, transparent Counter-Strike 2 match metrics."""

from importlib.metadata import version

from untraded.ratings import rating_hltv_1

__all__ = ["__version__", "rating_hltv_1"]
__version__ = version("untraded")
