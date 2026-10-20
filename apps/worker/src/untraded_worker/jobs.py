# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The job handlers, by kind. `parse` and `download` arrive in the next pull requests."""

from __future__ import annotations

from untraded_worker.runner import Handler

HANDLERS: dict[str, Handler] = {}
