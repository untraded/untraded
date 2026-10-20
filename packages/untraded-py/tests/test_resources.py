# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Live scheduling of a batch from the free RAM, and the parallel runner."""

from __future__ import annotations

import os

import pytest

from untraded import resources
from untraded.resources import GIB, Scheduler, run_adaptive

NOW = 1000.0


def scheduler(**kwargs: int) -> Scheduler:
    """12 CPUs, 2 GB per demo, 2 GB kept for the user."""
    defaults = {"cpus": 12, "total_memory": 8 * GIB, "task_memory": 2 * GIB}
    return Scheduler(**{**defaults, **kwargs})  # type: ignore[arg-type]


def test_reserve_is_15_percent_of_the_ram_and_at_least_2_gb() -> None:
    assert Scheduler(cpus=4, total_memory=32 * GIB).reserve == int(32 * GIB * 0.15)
    assert Scheduler(cpus=4, total_memory=8 * GIB).reserve == 2 * GIB
    assert Scheduler(cpus=4, total_memory=None).reserve == 2 * GIB


def test_first_demo_always_starts() -> None:
    assert scheduler().can_start(available=0, started=[], now=NOW)


def test_demos_start_while_the_free_ram_covers_them() -> None:
    s = scheduler()
    # 10 GB free: 2 GB reserve, then 2 GB for each demo started too recently to show.
    assert s.can_start(10 * GIB, started=[NOW, NOW, NOW], now=NOW)
    assert not s.can_start(10 * GIB, started=[NOW, NOW, NOW, NOW], now=NOW)


def test_started_demos_count_from_the_measure_once_ramped_up() -> None:
    s = scheduler()
    old = NOW - resources.RAMP_SECONDS - 1
    # Four old demos already show in the 4 GB measured: room for one more.
    assert s.can_start(4 * GIB, started=[old] * 4, now=NOW)
    assert not s.can_start(3 * GIB, started=[old] * 4, now=NOW)


def test_less_free_ram_stops_new_demos() -> None:
    s = scheduler()
    assert s.can_start(8 * GIB, started=[NOW - 60], now=NOW)
    assert not s.can_start(3 * GIB, started=[NOW - 60], now=NOW)


def test_never_more_demos_than_cpus() -> None:
    assert not scheduler(cpus=2).can_start(64 * GIB, started=[NOW - 60] * 2, now=NOW)


def test_unknown_ram_is_only_limited_by_the_cpus() -> None:
    s = scheduler(cpus=3)
    assert s.can_start(None, started=[NOW, NOW], now=NOW)
    assert not s.can_start(None, started=[NOW, NOW, NOW], now=NOW)


def test_threads_share_the_cpus_between_the_demos_expected_to_run() -> None:
    s = scheduler()
    # 10 GB free, 2 GB reserve: 4 demos fit, 3 threads each.
    assert s.threads(10 * GIB, started=[], now=NOW) == 3
    # Tight RAM: this demo will run alone.
    assert s.threads(4 * GIB, started=[], now=NOW) == 12
    assert s.threads(None, started=[], now=NOW) == 12


def test_demo_memory_is_learned_from_the_largest_peak() -> None:
    s = scheduler()
    s.observe(1 * GIB)
    s.observe(None)
    assert s.task_memory == int(1 * GIB * resources.PEAK_MARGIN)
    s.observe(3 * GIB)
    s.observe(2 * GIB)
    assert s.task_memory == int(3 * GIB * resources.PEAK_MARGIN)


def test_this_machine_is_measured() -> None:
    assert resources.cpu_count() >= 1
    for value in (resources.available_memory(), resources.total_memory(), resources.peak_memory()):
        assert value is None or value > 0


@pytest.mark.parametrize("jobs", [None, 1, 2])
def test_run_adaptive_returns_every_result_with_its_index(jobs: int | None) -> None:
    results = dict(run_adaptive(abs, [-3, 1, -7, 0], jobs=jobs, memory=lambda: 64 * GIB))
    assert results == {0: 3, 1: 1, 2: 7, 3: 0}


def test_run_adaptive_makes_progress_without_free_ram() -> None:
    starts: list[int] = []
    results = dict(
        run_adaptive(abs, [-1, -2, -3], memory=lambda: 0, on_start=lambda i, n, t: starts.append(n))
    )
    assert results == {0: 1, 1: 2, 2: 3}
    assert starts == [1, 1, 1]  # one at a time


def test_run_adaptive_raises_the_first_failure() -> None:
    with pytest.raises(ValueError, match="not a number"):
        list(run_adaptive(int, ["1", "not a number", "3"], jobs=2))


def test_workers_get_thread_limits_and_the_parent_keeps_its_environment() -> None:
    before = {name: os.environ.get(name) for name in resources.THREAD_VARIABLES}
    seen = dict(run_adaptive(os.getenv, list(resources.THREAD_VARIABLES), jobs=2))
    for index, name in enumerate(resources.THREAD_VARIABLES):
        assert seen[index] == (before[name] or str(max(1, resources.cpu_count() // 2)))
    assert {name: os.environ.get(name) for name in resources.THREAD_VARIABLES} == before
