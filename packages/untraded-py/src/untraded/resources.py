# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""How much of the machine a batch of demos may use, and running the batch in parallel.

A batch runs one demo per worker process. The number of workers comes from the logical CPUs this
process may use and the RAM available when the batch starts, so a busy machine gets fewer
workers. Each worker also gets an equal share of the CPU budget for the thread pools of Polars
and demoparser2, so the workers do not fight over the cores. Standard library only.
"""

from __future__ import annotations

import ctypes
import os
import sys
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")

DEFAULT_SHARE = 0.6
"""Share of the CPUs and of the available RAM a batch may use."""

DEMO_MEMORY = 2 * 1024**3
"""Peak memory of one demo task (parse, derive, metrics): about 1.8 GB on a Premier match."""

THREAD_VARIABLES = ("POLARS_MAX_THREADS", "RAYON_NUM_THREADS")
"""Thread pool sizes read at import by Polars and by demoparser2 (Rayon)."""


@dataclass(frozen=True)
class Budget:
    workers: int
    threads_per_worker: int
    cpus: int
    available_memory: int | None

    def describe(self) -> str:
        memory = (
            f"{self.available_memory / 1024**3:.1f} GB RAM available"
            if self.available_memory is not None
            else "RAM unknown"
        )
        plural = "s" if self.workers > 1 else ""
        return (
            f"{self.workers} worker{plural} x {self.threads_per_worker} threads "
            f"({self.cpus} CPUs, {memory})"
        )


def cpu_count() -> int:
    """Logical CPUs this process may run on (CPU affinity and container limits included)."""
    if sys.version_info >= (3, 13):
        return os.process_cpu_count() or 1
    if hasattr(os, "sched_getaffinity"):
        return len(os.sched_getaffinity(0))
    return os.cpu_count() or 1


def available_memory() -> int | None:
    """RAM that can be used right now without swapping, in bytes; `None` if unknown."""
    if sys.platform == "win32":
        return _windows_available_memory()
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        for line in meminfo.read_text(encoding="ascii").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    # macOS and other Unix systems: the standard library only knows the total, an upper bound.
    try:
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, ValueError, OSError):
        return None


def _windows_available_memory() -> int | None:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    if sys.platform == "win32" and ctypes.windll.kernel32.GlobalMemoryStatusEx(
        ctypes.byref(status)
    ):
        return int(status.ullAvailPhys)
    return None


def plan(
    tasks: int,
    *,
    jobs: int | None = None,
    share: float = DEFAULT_SHARE,
    task_memory: int = DEMO_MEMORY,
    cpus: int | None = None,
    memory: int | None = None,
) -> Budget:
    """Workers for `tasks` demos: `jobs` if given, else as many as `share` of the CPUs and of the
    available RAM allow. Never fewer than 1 nor more than `tasks`.

    `cpus` and `memory` default to this machine (`cpu_count()`, `available_memory()`).
    """
    if not 0 < share <= 1:
        raise ValueError(f"share must be in (0, 1], got {share}")
    if jobs is not None and jobs < 1:
        raise ValueError(f"jobs must be at least 1, got {jobs}")
    cpus = cpu_count() if cpus is None else cpus
    if memory is None and jobs is None:
        memory = available_memory()
    cpu_budget = max(1, int(cpus * share))
    if jobs is not None:
        workers = jobs
    else:
        workers = cpu_budget
        if memory is not None:
            workers = min(workers, int(memory * share) // task_memory)
    workers = max(1, min(workers, tasks))
    return Budget(
        workers=workers,
        threads_per_worker=max(1, cpu_budget // workers),
        cpus=cpus,
        available_memory=memory,
    )


def run_parallel(
    fn: Callable[[T], R], items: Sequence[T], budget: Budget
) -> Iterator[tuple[int, R]]:
    """Yields `(index, fn(item))` as each item finishes, in completion order.

    With one worker, items run in this process, in order. `fn` must be a module-level function
    (it is pickled to the workers). The first failure is raised and the pending items cancelled.
    """
    if budget.workers == 1:
        for index, item in enumerate(items):
            yield index, fn(item)
        return
    with (
        _thread_limits(budget.threads_per_worker),
        ProcessPoolExecutor(max_workers=budget.workers) as pool,
    ):
        futures = {pool.submit(fn, item): index for index, item in enumerate(items)}
        try:
            for future in as_completed(futures):
                yield futures[future], future.result()
        except BaseException:
            pool.shutdown(wait=True, cancel_futures=True)
            raise


@contextmanager
def _thread_limits(threads: int) -> Iterator[None]:
    """Sets the thread pool sizes inherited by the worker processes, unless the user set them."""
    previous = {name: os.environ.get(name) for name in THREAD_VARIABLES}
    for name, value in previous.items():
        if value is None:
            os.environ[name] = str(threads)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
