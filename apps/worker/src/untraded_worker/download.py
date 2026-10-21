# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Downloads a demo over HTTP, resuming interrupted transfers.

Valve replay servers throttle each connection (about 50 to 170 KB/s, spike S0.1) and drop it
every few MB, so the transfer resumes with `Range` requests and goes on while bytes arrive. The
`.part` file stays between attempts, and between jobs, so a retried job resumes too.

Demo URLs will also come from users (uploads by URL, FACEIT): a download never reaches a
private, loopback, link-local (cloud metadata) or reserved address. The address is checked when
the connection opens, on every redirect, so a name that resolves elsewhere the second time, or
a redirect to an internal host, is refused too. `UNTRADED_ALLOW_PRIVATE_DEMO_URLS=1` lifts it,
for a self-hosted setup that fetches demos from its own network (a MatchZy server on the LAN).
"""

from __future__ import annotations

import http.client
import ipaddress
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CHUNK = 1 << 16
READ_TIMEOUT_S = 60.0
"""A connection that sends nothing for this long is dropped (and resumed)."""
MAX_TRIES_WITHOUT_PROGRESS = 5
RETRY_DELAY_S = 5.0
GONE = frozenset({404, 410})
"""Statuses meaning the demo no longer exists (Valve deletes demos after about 30 days)."""


class DownloadError(OSError):
    """The download failed for now; the job is retried later."""


class DemoGone(Exception):  # noqa: N818 (an outcome, not a failure)
    """The server says the demo does not exist (any more)."""

    def __init__(self, status: int) -> None:
        super().__init__(f"HTTP {status}")
        self.status = status


@dataclass(frozen=True)
class Downloaded:
    bytes: int
    tries: int
    resumed: bool


class BlockedAddressError(ValueError):
    """The URL leads to an address a download must not reach."""


def check_url(url: str) -> None:
    """Only http(s) URLs are fetched."""
    if urllib.parse.urlsplit(url).scheme not in {"http", "https"}:
        raise ValueError(f"not an http(s) URL: {url!r}")


def allow_private() -> bool:
    return os.environ.get("UNTRADED_ALLOW_PRIVATE_DEMO_URLS") == "1"


def public(address: str) -> bool:
    """Whether a download may connect to this IP: global unicast only."""
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def fetch(
    url: str,
    target: Path,
    *,
    retry_delay_s: float = RETRY_DELAY_S,
    private: bool | None = None,
) -> Downloaded:
    """Downloads `url` to `target` through `target.part`. Raises DemoGone or DownloadError, or
    BlockedAddressError when the URL (or a redirect) leads to a non-public address and `private`
    (default: `UNTRADED_ALLOW_PRIVATE_DEMO_URLS`) is not set."""
    check_url(url)
    opener = _opener(allow_private() if private is None else private)
    partial = target.with_name(target.name + ".part")
    partial.parent.mkdir(parents=True, exist_ok=True)
    resumed = partial.exists() and partial.stat().st_size > 0
    tries = without_progress = 0
    while True:
        tries += 1
        have = partial.stat().st_size if partial.exists() else 0
        try:
            if _transfer(opener, url, partial, have):
                break
            error = "short read"
        except (DemoGone, BlockedAddressError):
            raise
        except (OSError, http.client.HTTPException) as failure:  # URLError is an OSError
            error = str(failure)
        now = partial.stat().st_size if partial.exists() else 0
        without_progress = 0 if now > have else without_progress + 1
        if without_progress >= MAX_TRIES_WITHOUT_PROGRESS:
            raise DownloadError(f"{error} (at {now} bytes, after {tries} tries)")
        time.sleep(retry_delay_s)
    partial.replace(target)
    return Downloaded(bytes=target.stat().st_size, tries=tries, resumed=resumed)


def _transfer(opener: urllib.request.OpenerDirector, url: str, partial: Path, have: int) -> bool:
    """One request; True when the file is complete."""
    request = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    try:
        # A BlockedAddressError is no OSError: urllib lets it through as is.
        response = opener.open(request, timeout=READ_TIMEOUT_S)
    except urllib.error.HTTPError as error:
        if error.code in GONE:
            raise DemoGone(error.code) from error
        if error.code == 416 and have:  # nothing left after `have`: already complete
            return True
        raise
    with response:
        # 206 continues the file; 200 means the server ignored Range: start over.
        append = response.status == 206
        expected = response.headers.get("Content-Length")
        total = (have if append else 0) + int(expected) if expected is not None else None
        with partial.open("ab" if append else "wb") as out:
            while chunk := response.read(CHUNK):
                out.write(chunk)
    return total is None or partial.stat().st_size == total


def _opener(private: bool) -> urllib.request.OpenerDirector:
    """No proxy from the environment (it would hide the real address), and when `private` is
    false, connections that check the address they open."""
    if private:
        return urllib.request.build_opener(urllib.request.ProxyHandler({}), _Redirects())
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _Redirects(), _GuardedHTTP(), _GuardedHTTPS()
    )


def _guarded_connection(
    address: tuple[str, int], timeout: float | None = None, source_address: object = None
) -> socket.socket:
    """`socket.create_connection`, to the first public address of the name only."""
    host, port = address
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    allowed = [info for info in infos if public(str(info[4][0]))]
    if not allowed:
        raise BlockedAddressError(f"{host} does not resolve to a public address")
    family, kind, proto, _, sockaddr = allowed[0]
    sock = socket.socket(family, kind, proto)
    try:
        if timeout is not None:
            sock.settimeout(timeout)
        sock.connect(sockaddr)
    except OSError:
        sock.close()
        raise
    return sock


class _GuardedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Set per instance by http.client (`socket.create_connection`): replaced the same way.
        self._create_connection = _guarded_connection


class _GuardedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._create_connection = _guarded_connection


class _GuardedHTTP(urllib.request.HTTPHandler):
    def http_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        return self.do_open(_GuardedHTTPConnection, req)


class _GuardedHTTPS(urllib.request.HTTPSHandler):
    def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        return self.do_open(_GuardedHTTPSConnection, req, context=self._context)


class _Redirects(urllib.request.HTTPRedirectHandler):
    """Redirects stay on http(s); the guarded connections check where they lead."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)
