# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Worker budget from the machine's CPUs and RAM, and the parallel runner."""

from __future__ import annotations

import os

import pytest

from untraded import resources
from untraded.resources import Budget, plan, run_parallel

GB = 1024**3


def test_cpu_bound_machine_uses_its_share_of_the_cpus() -> None:
    budget = plan(30, cpus=12, memory=64 * GB, task_memory=2 * GB)
    assert budget.workers == 7  # 60 % of 12
    assert budget.threads_per_worker == 1


def test_memory_bound_machine_gets_fewer_workers() -> None:
    budget = plan(30, cpus=12, memory=8 * GB, task_memory=2 * GB)
    assert budget.workers == 2  # 60 % of 8 GB = 4.8 GB, two demos of 2 GB
    assert budget.threads_per_worker == 3  # the 7 cores of the budget are shared


def test_never_fewer_than_one_worker() -> None:
    budget = plan(30, cpus=1, memory=1 * GB, task_memory=2 * GB)
    assert budget.workers == 1
    assert budget.threads_per_worker == 1


def test_never_more_workers_than_demos() -> None:
    assert plan(3, cpus=32, memory=256 * GB).workers == 3


def test_unknown_memory_only_limits_by_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resources, "available_memory", lambda: None)
    assert plan(30, cpus=10, share=0.5).workers == 5


def test_jobs_overrides_the_budget() -> None:
    budget = plan(30, jobs=4, cpus=12, memory=1 * GB)
    assert budget.workers == 4
    assert budget.threads_per_worker == 1


@pytest.mark.parametrize("kwargs", [{"share": 0.0}, {"share": 1.5}, {"jobs": 0}])
def test_invalid_settings_are_rejected(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="must be"):
        plan(30, cpus=4, memory=8 * GB, **kwargs)  # type: ignore[arg-type]


def test_this_machine_is_measured() -> None:
    assert resources.cpu_count() >= 1
    memory = resources.available_memory()
    assert memory is None or memory > 0


@pytest.mark.parametrize("workers", [1, 2])
def test_run_parallel_returns_every_result_with_its_index(workers: int) -> None:
    budget = Budget(workers=workers, threads_per_worker=1, cpus=2, available_memory=None)
    results = dict(run_parallel(abs, [-3, 1, -7, 0], budget))
    assert results == {0: 3, 1: 1, 2: 7, 3: 0}


def test_run_parallel_raises_the_first_failure() -> None:
    budget = Budget(workers=2, threads_per_worker=1, cpus=2, available_memory=None)
    with pytest.raises(ValueError, match="not a number"):
        list(run_parallel(int, ["1", "not a number", "3"], budget))


def test_thread_limits_are_set_for_the_workers_then_restored() -> None:
    before = {name: os.environ.get(name) for name in resources.THREAD_VARIABLES}
    budget = Budget(workers=2, threads_per_worker=3, cpus=6, available_memory=None)
    seen = dict(run_parallel(os.getenv, ["POLARS_MAX_THREADS", "RAYON_NUM_THREADS"], budget))
    expected = {i: before[name] or "3" for i, name in enumerate(resources.THREAD_VARIABLES)}
    assert seen == expected
    assert {name: os.environ.get(name) for name in resources.THREAD_VARIABLES} == before
