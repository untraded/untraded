# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The worker loop: claim a job, run its handler, record the outcome, wait for the next one.

The claim commits on its own: the job is `running` and the attempt counts, even if the worker
dies during the job: it counts as a failed attempt (with its backoff) when the worker starts
again, or after `queue.STALE_AFTER` for any worker, which looks every `queue.STALE_EVERY`; it
ends `dead` once its attempts are used up, instead of crashing workers forever. The handler's
writes and the job's completion then commit together; a failure rolls them back and is
recorded. Between jobs, the worker sleeps on `LISTEN job_<kind>` (the queue's insert trigger,
ADR 0004), with a timeout as a fallback.
"""

from __future__ import annotations

import datetime as dt
import logging
import signal
import socket
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg import sql

from untraded_worker import queue
from untraded_worker.queue import Job

Handler = Callable[[psycopg.Connection[Any], Job], None]
"""Runs one job inside a transaction that also marks the job done."""
DeadHandler = Callable[[psycopg.Connection[Any], Job, str], None]
"""Called when a job of its kind dies (no attempt left), with the error, in the transaction
that records it: e.g. to mark the match `failed`."""

POLL_SECONDS = 30.0


@dataclass
class Periodic:
    """Housekeeping run when the worker is idle, at most every `interval` (e.g. retention)."""

    interval: dt.timedelta
    run: Callable[[psycopg.Connection[Any]], object]
    last: float | None = None

    def due(self, now: float) -> bool:
        return self.last is None or now - self.last >= self.interval.total_seconds()


STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM)
log = logging.getLogger("untraded.worker")


@dataclass
class Worker:
    conninfo: str
    handlers: Mapping[str, Handler]
    on_dead: Mapping[str, DeadHandler] = field(default_factory=dict)
    periodic: Sequence[Periodic] = ()
    name: str = field(default_factory=socket.gethostname)
    poll_seconds: float = POLL_SECONDS
    stopping: bool = False
    recovered_at: float = field(default_factory=time.monotonic)

    def run(self, *, once: bool = False) -> int:
        """Processes jobs until stopped (SIGINT, SIGTERM); with `once`, until no job is ready.
        Returns the number of jobs processed."""
        previous = {sig: signal.signal(sig, lambda *_: self.stop()) for sig in STOP_SIGNALS}
        try:
            return self._loop(once)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)

    def _loop(self, once: bool) -> int:
        processed = 0
        with (
            psycopg.connect(self.conninfo, autocommit=True) as conn,
            psycopg.connect(self.conninfo, autocommit=True) as listener,
        ):
            for kind in self.handlers:
                listener.execute(sql.SQL("LISTEN {}").format(sql.Identifier(f"job_{kind}")))
            for mine in (True, False):
                try:
                    self.recover(conn, mine=mine)
                except Exception:  # a failing dead handler must not stop the worker for good
                    log.exception("taking back abandoned jobs failed")
            while not self.stopping:
                if self.step(conn):
                    processed += 1
                    continue
                self.idle(conn)
                if once:
                    break
                for _ in listener.notifies(timeout=self.poll_seconds, stop_after=1):
                    pass
        return processed

    def recover(self, conn: psycopg.Connection[Any], *, mine: bool) -> int:
        """Records the jobs abandoned by this worker (`mine`, as it starts: they were cut by its
        restart) or by a worker that is gone as failed attempts; returns how many."""
        error = "cut by a restart of its worker" if mine else "abandoned by its worker"
        with conn.transaction():
            jobs = queue.abandoned(conn, worker=self.name if mine else None)
            for job in jobs:
                if queue.fail(conn, job, error) and job.kind in self.on_dead:
                    self.on_dead[job.kind](conn, job, error)
        if jobs:
            log.warning("%s abandoned job(s): %s", len(jobs), error)
        return len(jobs)

    def idle(self, conn: psycopg.Connection[Any]) -> None:
        """Runs the periodic tasks that are due; a failing one is logged, not fatal."""
        now = time.monotonic()
        if now - self.recovered_at >= queue.STALE_EVERY.total_seconds():
            self.recovered_at = now
            try:
                self.recover(conn, mine=False)
            except Exception:
                log.exception("looking for abandoned jobs failed")
        for task in self.periodic:
            now = time.monotonic()
            if not task.due(now):
                continue
            task.last = now
            try:
                task.run(conn)
            except Exception:
                log.exception("periodic task failed")

    def stop(self) -> None:
        self.stopping = True

    def step(self, conn: psycopg.Connection[Any]) -> bool:
        """Claims and runs one job; False when no job is ready."""
        with conn.transaction():
            job = queue.claim(conn, list(self.handlers), self.name)
        if job is None:
            return False
        log.info("job %s (%s) started, attempt %s", job.id, job.kind, job.attempts)
        try:
            with conn.transaction():
                self.handlers[job.kind](conn, job)
                queue.complete(conn, job)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as error:  # a Rust panic (demoparser2) is a BaseException
            description = _describe(error)
            with conn.transaction():
                dead = queue.fail(conn, job, description)
                if dead and job.kind in self.on_dead:
                    self.on_dead[job.kind](conn, job, description)
            log.warning("job %s failed%s: %s", job.id, " (dead)" if dead else "", error)
            return True
        log.info("job %s done", job.id)
        return True


def _describe(error: BaseException) -> str:
    lines = traceback.format_exception(error)
    return f"{type(error).__name__}: {error}\n{''.join(lines[-6:])}"
