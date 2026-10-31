# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Parsing a demo in a child process, with a deadline.

A demo comes from a player or a server we do not control. The parser (native code) could hang
on a strange one, or eat all the memory: in the worker's own process, that would stop the whole
queue, or have the kernel kill the worker. In a child process, a parse past its deadline is
killed and the job fails like any other (retried, then `dead`); a child killed for memory (the
worker's `mem_limit` in compose.yaml) fails the job the same way, and the worker goes on.

The worker sweeps the temporary directories of children it could not clean up (killed with it)
when it starts (`sweep_leftovers`).

The child writes the canonical tables as Parquet in a temporary directory, which the worker
reads back: no large object crosses the pipe.
"""

from __future__ import annotations

import multiprocessing
import os
import shutil
import tempfile
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any

from untraded.parsing import CanonicalMatch, UnsupportedModeError, parse_demo

VARIABLE = "UNTRADED_PARSE_TIMEOUT_SECONDS"
DEFAULT_TIMEOUT = 600.0
"""A parse takes about a minute on the beta server: ten is a demo the parser is stuck on."""


class ParseError(RuntimeError):
    """The child did not finish: killed (out of memory), or crashed."""


class ParseTimeoutError(ParseError):
    """The parse went past its deadline: the demo is one the parser gets stuck on, so trying
    again would only hold the queue as long again."""


PREFIX = "untraded-parse-"


def sweep_leftovers() -> int:
    """Deletes the temporary directories of parses that died with their worker; returns how
    many. Only one worker runs per container: none of them is in use as it starts."""
    root = Path(tempfile.gettempdir())
    gone = 0
    for leftover in root.glob(f"{PREFIX}*"):
        shutil.rmtree(leftover, ignore_errors=True)
        gone += 1
    return gone


def configured_timeout() -> float:
    value = os.environ.get(VARIABLE, "").strip()
    seconds = float(value) if value else DEFAULT_TIMEOUT
    if seconds <= 0:
        raise ValueError(f"{VARIABLE} must be > 0, got {value}")
    return seconds


def _child(
    parse: Callable[..., CanonicalMatch],
    path: Path,
    kwargs: dict[str, Any],
    out: Path,
    pipe: Connection,
) -> None:
    # The decompressed demo and every other temporary file go under `out`, which the worker
    # deletes even when it kills this process (a killed process cleans nothing up).
    tempfile.tempdir = str(out)
    os.environ["TMPDIR"] = str(out)
    try:
        parse(path, **kwargs).write(out)
        pipe.send(("ok", ""))
    except UnsupportedModeError as error:
        pipe.send(("unsupported", str(error)))
    except BaseException:  # everything goes back to the worker, as text
        pipe.send(("error", traceback.format_exc()))
    finally:
        pipe.close()


@dataclass(frozen=True)
class IsolatedParse:
    """`parse_demo` in a child process (same arguments), killed after `timeout` seconds."""

    parse: Callable[..., CanonicalMatch] = parse_demo
    timeout: float = field(default_factory=configured_timeout)

    def __call__(self, path: Path, **kwargs: Any) -> CanonicalMatch:
        context = multiprocessing.get_context("spawn")  # no state inherited from the worker
        with tempfile.TemporaryDirectory(prefix=PREFIX) as tmp:
            receive, send = context.Pipe(duplex=False)
            child = context.Process(
                target=_child,
                args=(self.parse, path, kwargs, Path(tmp), send),
                name="untraded-parse",
                daemon=True,
            )
            child.start()
            send.close()  # only the child holds it now: its death ends the pipe
            try:
                if not receive.poll(self.timeout):
                    raise ParseTimeoutError(f"the parse took over {self.timeout:.0f} s: stopped")
                try:
                    outcome, detail = receive.recv()
                except EOFError:
                    child.join(5)
                    raise ParseError(
                        f"the parser died (exit code {child.exitcode}; out of memory if -9)"
                    ) from None
            finally:
                if child.is_alive():
                    child.kill()
                child.join(5)
                receive.close()
            if outcome == "unsupported":
                raise UnsupportedModeError(detail)
            if outcome != "ok":
                cause = detail.strip().splitlines()[-1] if detail.strip() else "?"
                # The cause first: the job's recorded error is cut at 4000 characters.
                raise ParseError(f"the parser failed: {cause}\n{detail}")
            matches = list((Path(tmp) / "matches").iterdir())
            if len(matches) != 1:
                raise ParseError(f"the parser wrote {len(matches)} matches, not one")
            return CanonicalMatch.read(matches[0])
