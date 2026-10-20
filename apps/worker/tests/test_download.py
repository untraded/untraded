# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""`download.fetch` against a local server that behaves like Valve's: it drops connections."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from untraded_worker.download import DemoGone, DownloadError, check_url, fetch

BODY = bytes(range(256)) * 400  # 100 KB


@dataclass
class Behaviour:
    drop_after: int | None = None
    """Bytes sent before dropping the connection, on every request."""
    ignore_range: bool = False
    status: int = 200
    ranges: list[str | None] = field(default_factory=list)


@pytest.fixture
def server() -> Iterator[tuple[str, Behaviour]]:
    behaviour = Behaviour()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requested = self.headers.get("Range")
            behaviour.ranges.append(requested)
            if behaviour.status != 200:
                self.send_error(behaviour.status)
                return
            start = 0
            if requested and not behaviour.ignore_range:
                start = int(requested.removeprefix("bytes=").rstrip("-"))
            body = BODY[start:]
            self.send_response(206 if start else 200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if behaviour.drop_after is not None:
                body = body[: behaviour.drop_after]
            self.wfile.write(body)
            self.close_connection = True

        def log_message(self, *_: object) -> None:
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/730/123_456.dem.bz2", behaviour
    httpd.shutdown()
    httpd.server_close()


def test_plain_download(server: tuple[str, Behaviour], tmp_path: Path) -> None:
    url, behaviour = server
    result = fetch(url, tmp_path / "demo.dem.bz2", retry_delay_s=0)
    assert (tmp_path / "demo.dem.bz2").read_bytes() == BODY
    assert (result.bytes, result.tries, result.resumed) == (len(BODY), 1, False)
    assert behaviour.ranges == [None]
    assert not (tmp_path / "demo.dem.bz2.part").exists()


def test_dropped_connections_are_resumed(server: tuple[str, Behaviour], tmp_path: Path) -> None:
    url, behaviour = server
    behaviour.drop_after = 30_000
    result = fetch(url, tmp_path / "demo.dem.bz2", retry_delay_s=0)
    assert (tmp_path / "demo.dem.bz2").read_bytes() == BODY
    assert result.tries == 4
    assert behaviour.ranges == [None, "bytes=30000-", "bytes=60000-", "bytes=90000-"]


def test_a_partial_file_from_an_earlier_job_is_resumed(
    server: tuple[str, Behaviour], tmp_path: Path
) -> None:
    url, behaviour = server
    (tmp_path / "demo.dem.bz2.part").write_bytes(BODY[:1000])
    assert fetch(url, tmp_path / "demo.dem.bz2", retry_delay_s=0).resumed
    assert (tmp_path / "demo.dem.bz2").read_bytes() == BODY
    assert behaviour.ranges == ["bytes=1000-"]


def test_a_server_ignoring_range_restarts_the_file(
    server: tuple[str, Behaviour], tmp_path: Path
) -> None:
    url, behaviour = server
    behaviour.ignore_range = True
    (tmp_path / "demo.dem.bz2.part").write_bytes(b"stale")
    fetch(url, tmp_path / "demo.dem.bz2", retry_delay_s=0)
    assert (tmp_path / "demo.dem.bz2").read_bytes() == BODY


def test_no_progress_gives_up(server: tuple[str, Behaviour], tmp_path: Path) -> None:
    url, behaviour = server
    behaviour.drop_after = 0
    with pytest.raises(DownloadError, match="after 5 tries"):
        fetch(url, tmp_path / "demo.dem.bz2", retry_delay_s=0)


@pytest.mark.parametrize("status", [404, 410])
def test_a_gone_demo(server: tuple[str, Behaviour], tmp_path: Path, status: int) -> None:
    url, behaviour = server
    behaviour.status = status
    with pytest.raises(DemoGone) as gone:
        fetch(url, tmp_path / "demo.dem.bz2", retry_delay_s=0)
    assert gone.value.status == status


def test_a_server_error_is_retried_then_fails(
    server: tuple[str, Behaviour], tmp_path: Path
) -> None:
    url, behaviour = server
    behaviour.status = 503
    with pytest.raises(DownloadError):
        fetch(url, tmp_path / "demo.dem.bz2", retry_delay_s=0)
    assert len(behaviour.ranges) == 5


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://x/demo.dem", "demo.dem"])
def test_only_http_urls(url: str) -> None:
    with pytest.raises(ValueError, match="not an http"):
        check_url(url)
