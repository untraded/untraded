# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The worker loop: claim a job, run its handler, record the outcome, wait for the next one.

The claim commits on its own: the job is `running` and the attempt counts, even if the worker
dies during the job (it is then put back in the queue after `queue.STALE_AFTER`, and ends `dead`
once its attempts are used up, instead of crashing workers forever). The handler's writes and
the job's completion then commit together; a failure rolls them back and is recorded. Between
jobs, the worker sleeps on `LISTEN job_<kind>` (the queue's insert trigger, ADR 0004), with a
timeout as a fallback.
"""

from __future__ import annotations

import logging
import signal
import socket
import traceback
from collections.abc import Callable, Mapping
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
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM)
log = logging.getLogger("untraded.worker")


@dataclass
class Worker:
    conninfo: str
    handlers: Mapping[str, Handler]
    on_dead: Mapping[str, DeadHandler] = field(default_factory=dict)
    name: str = field(default_factory=socket.gethostname)
    poll_seconds: float = POLL_SECONDS
    stopping: bool = False

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
            stale = queue.requeue_stale(conn)
            if stale:
                log.warning("%s abandoned job(s) put back in the queue", stale)
            while not self.stopping:
                if self.step(conn):
                    processed += 1
                    continue
                if once:
                    break
                for _ in listener.notifies(timeout=self.poll_seconds, stop_after=1):
                    pass
        return processed

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
