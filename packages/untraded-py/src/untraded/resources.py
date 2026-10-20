# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Run a batch of demos in parallel, adapting to the machine while it runs.

- CPU: workers run at low priority, so they use every idle core and the OS hands the cores back
  to the user's applications at once. There is no CPU cap besides one demo per logical CPU.
- RAM: a demo starts only if the RAM available right now covers it on top of a reserve kept for
  the user. Memory frees up, more demos run; it gets tight, no demo starts until it frees up.
  A running demo is never stopped: the batch adapts at demo boundaries.
- The memory a demo needs, and how long it keeps growing, are learned from the finished demos.
- A failing demo does not stop the batch when the caller handles failures (`on_error`).

Each demo runs in a fresh process, so its memory is returned to the system when it ends and its
thread pools (Polars, Rayon in demoparser2) are sized for the number of demos running when it
starts. Standard library only.
"""

from __future__ import annotations

import ctypes
import multiprocessing
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")

GIB = 1024**3
DEMO_MEMORY = 2 * GIB
"""First guess for the peak memory of one demo, before any has finished (measured: 1.75 GB)."""
PEAK_MARGIN = 1.15
"""Margin on the largest measured peak."""
RAMP_SECONDS = 20.0
"""A demo started less than this ago may not have allocated its memory yet: it stays reserved.
Raised to the longest finished demo, since a demo keeps allocating until it ends."""
POLL_SECONDS = 1.0
"""How often the RAM is checked again while a demo waits for memory."""
THREAD_VARIABLES = ("POLARS_MAX_THREADS", "RAYON_NUM_THREADS")
"""Thread pool sizes read at import by Polars and by demoparser2 (Rayon)."""


# --- Measuring the machine ------------------------------------------------------------------


def cpu_count() -> int:
    """Logical CPUs this process may run on (CPU affinity included; container CPU quotas are
    not)."""
    if sys.version_info >= (3, 13):
        return os.process_cpu_count() or 1
    if hasattr(os, "sched_getaffinity"):
        return len(os.sched_getaffinity(0))
    return os.cpu_count() or 1


def available_memory() -> int | None:
    """RAM that can be used right now without swapping, in bytes; `None` if unknown."""
    if sys.platform == "win32":
        return _windows_memory()[0]
    if sys.platform == "darwin":
        return _macos_available_memory()
    return _meminfo("MemAvailable")


def total_memory() -> int | None:
    """Physical RAM, in bytes; `None` if unknown."""
    if sys.platform == "win32":
        return _windows_memory()[1]
    try:
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, ValueError, OSError):
        return _meminfo("MemTotal")


def _meminfo(key: str) -> int | None:
    try:
        lines = Path("/proc/meminfo").read_text(encoding="ascii").splitlines()
    except OSError:
        return None
    for line in lines:
        if line.startswith(f"{key}:"):
            return int(line.split()[1]) * 1024
    return None


def _macos_available_memory() -> int | None:
    """Free, inactive, speculative and purgeable pages, as reported by `vm_stat`."""
    try:
        output = subprocess.run(["vm_stat"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    lines = output.splitlines()
    try:
        page_size = int(lines[0].split("page size of")[1].split()[0]) if lines else 4096
        pages = 0
        for line in lines[1:]:
            name, _, value = line.partition(":")
            if name in ("Pages free", "Pages inactive", "Pages speculative", "Pages purgeable"):
                pages += int(value.strip().rstrip("."))
    except (IndexError, ValueError):
        return None
    return pages * page_size


def _windows_memory() -> tuple[int | None, int | None]:
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
        return int(status.ullAvailPhys), int(status.ullTotalPhys)
    return None, None


def peak_memory() -> int | None:
    """Peak resident memory of this process so far, plus its largest finished child process
    on Linux and macOS (the CS Demo Manager analyzer), in bytes; `None` if unknown. On Windows,
    children are not measured: the scheduler never goes below its first guess."""
    if sys.platform == "win32":

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.K32GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(Counters),
            ctypes.c_ulong,
        ]
        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        if kernel32.K32GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            return int(counters.PeakWorkingSetSize)
        return None
    import resource

    peak = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        + resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    )
    return peak if sys.platform == "darwin" else peak * 1024  # bytes on macOS, KiB elsewhere


def lower_priority() -> None:
    """Runs this process (and the programs it starts) below the user's applications."""
    if sys.platform == "win32":
        below_normal = 0x00004000
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), below_normal)
    else:
        os.nice(10)


# --- Deciding when a demo may start ---------------------------------------------------------


@dataclass
class Scheduler:
    """Decides, from the RAM available right now, whether one more demo may start.

    Pure logic: the caller passes the measurements, so it can be tested without a real machine.
    """

    cpus: int
    total_memory: int | None
    task_memory: int = DEMO_MEMORY
    reserve: int = field(default=0)
    ramp_seconds: float = RAMP_SECONDS
    _peaks: list[int] = field(default_factory=list)
    _floor: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._floor = self.task_memory
        if not self.reserve:
            # Kept free for the user: 15 % of the RAM, at least 2 GB.
            share = int(self.total_memory * 0.15) if self.total_memory else 0
            self.reserve = max(2 * GIB, share)

    def headroom(self, available: int, started: Sequence[float], now: float) -> int:
        """RAM a new demo could use: available, minus the reserve, minus the demos that started
        too recently to show in `available`."""
        ramping = sum(1 for t in started if now - t < self.ramp_seconds)
        return available - self.reserve - ramping * self.task_memory

    def can_start(self, available: int | None, started: Sequence[float], now: float) -> bool:
        running = len(started)
        if running == 0:
            return True  # always make progress
        if running >= self.cpus:
            return False
        if available is None:
            return True  # RAM unknown: only the CPUs limit
        return self.headroom(available, started, now) >= self.task_memory

    def threads(self, available: int | None, started: Sequence[float], now: float) -> int:
        """Thread pool size for a demo starting now: the CPUs shared by the demos expected to run
        together, i.e. those running plus as many more as the RAM allows."""
        expected = len(started) + 1
        if available is not None:
            room = self.headroom(available, started, now) - self.task_memory
            expected += max(0, room // self.task_memory)
        return max(1, self.cpus // min(expected, self.cpus))

    def observe(self, peak: int | None, seconds: float | None = None) -> None:
        """Learns from a finished demo: its peak memory (never below the first guess, since a
        child process may not be measured) and its duration (a running demo stays reserved that
        long, as it keeps allocating until it ends)."""
        if peak:
            self._peaks.append(peak)
            self.task_memory = max(self._floor, int(max(self._peaks) * PEAK_MARGIN))
        if seconds is not None:
            self.ramp_seconds = max(self.ramp_seconds, seconds)


# --- Running the batch ----------------------------------------------------------------------


class TaskError(RuntimeError):
    """An item of the batch failed: `index` says which one, the cause is chained."""

    def __init__(self, index: int, cause: BaseException) -> None:
        super().__init__(f"item {index}: {_describe(cause)}")
        self.index = index
        self.__cause__ = cause


def _describe(error: BaseException) -> str:
    if isinstance(error, BrokenProcessPool):
        return "its worker process died (out of memory?)"
    if isinstance(error, WorkerError):
        return str(error)
    return f"{type(error).__name__}: {error}"


class WorkerError(RuntimeError):
    """The error of an item, as text: some exceptions cannot cross processes (a Rust panic in
    demoparser2 is a `PanicException`, which neither pickles nor derives from `Exception`)."""


def _call(fn: Callable[[T], R], item: T) -> R:
    try:
        return fn(item)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as error:
        first_line = str(error).splitlines()[0] if str(error) else ""
        raise WorkerError(f"{type(error).__name__}: {first_line}") from None


def _measured(fn: Callable[[T], R], item: T) -> tuple[R, int | None, float]:
    start = time.monotonic()
    result = _call(fn, item)
    return result, peak_memory(), time.monotonic() - start


def run_adaptive(
    fn: Callable[[T], R],
    items: Sequence[T],
    *,
    jobs: int | None = None,
    scheduler: Scheduler | None = None,
    memory: Callable[[], int | None] = available_memory,
    on_start: Callable[[int, int, int], None] | None = None,
    on_error: Callable[[TaskError], None] | None = None,
) -> Iterator[tuple[int, R]]:
    """Yields `(index, fn(item))` as each item finishes, in completion order.

    With `jobs`, exactly that many items run at once; otherwise the `scheduler` decides, from
    `memory()`, when the next one starts. `fn` must be a module-level function (it is pickled to
    the worker processes). `on_start(index, running, threads)` is called as each item starts.
    A failure becomes a `TaskError` naming the item. With `on_error`, it is passed there and the
    batch goes on; without, it is raised once the running items have finished, and the others
    never start.
    """
    if jobs == 1 or len(items) <= 1:
        for index, item in enumerate(items):
            if on_start:
                on_start(index, 1, 0)
            try:
                result = _call(fn, item)
            except Exception as error:
                if on_error is None:
                    raise TaskError(index, error) from error
                on_error(TaskError(index, error))
                continue
            yield index, result
        return
    scheduler = scheduler or Scheduler(cpus=cpu_count(), total_memory=total_memory())
    context = multiprocessing.get_context("spawn")
    pending = list(enumerate(items))
    running: dict[Future[tuple[R, int | None, float]], tuple[int, float, ProcessPoolExecutor]] = {}
    try:
        while pending or running:
            now = time.monotonic()
            started = [t for _, t, _ in running.values()]
            available = None if jobs else memory()
            ready = len(running) < jobs if jobs else scheduler.can_start(available, started, now)
            if pending and ready:
                index, item = pending.pop(0)
                threads = (
                    max(1, scheduler.cpus // jobs)
                    if jobs
                    else scheduler.threads(available, started, now)
                )
                executor = _start_worker(context, threads)
                running[executor.submit(_measured, fn, item)] = (index, now, executor)
                if on_start:
                    on_start(index, len(running), threads)
                continue  # check right away whether another one fits
            done, _ = wait(
                running, timeout=None if not pending else POLL_SECONDS, return_when=FIRST_COMPLETED
            )
            for future in done:
                index, _, executor = running.pop(future)
                executor.shutdown(wait=False)
                try:
                    result, peak, seconds = future.result()
                except Exception as error:
                    if on_error is None:
                        raise TaskError(index, error) from error
                    on_error(TaskError(index, error))
                    continue
                scheduler.observe(peak, seconds)
                yield index, result
    finally:
        pending.clear()
        for _, _, executor in running.values():
            executor.shutdown(wait=True, cancel_futures=True)


def _start_worker(
    context: multiprocessing.context.SpawnContext, threads: int
) -> ProcessPoolExecutor:
    """One fresh low-priority process, its thread pools sized to `threads` unless the user set
    them. Spawned processes read the environment when they start, before importing Polars."""
    previous = {name: os.environ.get(name) for name in THREAD_VARIABLES}
    for name, value in previous.items():
        if value is None:
            os.environ[name] = str(threads)
    try:
        executor = ProcessPoolExecutor(
            max_workers=1, mp_context=context, initializer=lower_priority
        )
        # The process starts on the first submission; make it start now, with this environment.
        executor.submit(int).result()
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
    return executor
