# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests marked `db` run against PostgreSQL with the migrations applied, given by
UNTRADED_TEST_DATABASE_URL (CI sets it); without it, they are skipped. They empty the `job`
table: never point it at a database you care about."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest

URL_VARIABLE = "UNTRADED_TEST_DATABASE_URL"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get(URL_VARIABLE):
        return
    skip = pytest.mark.skip(reason=f"{URL_VARIABLE} is not set")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def conninfo() -> str:
    return os.environ[URL_VARIABLE].replace("postgresql+psycopg://", "postgresql://", 1)


@pytest.fixture
def conn(conninfo: str) -> Iterator[psycopg.Connection[Any]]:
    with psycopg.connect(conninfo, autocommit=True) as connection:
        connection.execute("TRUNCATE job")
        yield connection
