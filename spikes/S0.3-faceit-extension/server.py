# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Spike S0.3: local test server that receives FACEIT demo URLs from the extension.

POST /ingest/url {"source": "faceit", "url": "<signed URL>", "file": "...", "seen_at": <epoch s>}
answers 202 at once, then downloads the demo in the background (resuming with Range if the
connection drops), checks that it decompresses to a CS2 demo, and appends one line per demo to
out/ingest.jsonl. Signed URLs are never written to disk: only their host and expiry are logged.

Usage: python server.py [port]   (listens on 127.0.0.1 only; default port 8765)
"""

from __future__ import annotations

import contextlib
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from compression import zstd

OUT_DIR = Path(__file__).parent / "out"
DEMO_HOSTS = (".backblazeb2.com", ".faceit-cdn.net")
DEMO_PATH = re.compile(r"^/cs2/([\w-]+)\.dem\.zst$")
DEMO_MAGIC = b"PBDEMS2\0"
ATTEMPTS = 5
CHUNK = 1 << 20


def validate(url: str) -> str | None:
    """Returns the demo file name if the URL is a FACEIT demo on FACEIT's storage, else None."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not (parts.hostname or "").endswith(DEMO_HOSTS):
        return None
    match = DEMO_PATH.match(parts.path)
    return match.group(1) if match else None


def seconds_left(url: str, now: float) -> float | None:
    """Remaining validity of an S3 presigned URL (X-Amz-Date + X-Amz-Expires)."""
    query = parse_qs(urlsplit(url).query)
    try:
        signed = datetime.strptime(query["X-Amz-Date"][0], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        return signed.timestamp() + int(query["X-Amz-Expires"][0]) - now
    except (KeyError, ValueError):
        return None


def download(url: str, target: Path) -> tuple[int, int]:
    """Downloads url to target, resuming with Range when the connection drops.

    Returns (bytes, attempts).
    """
    part = target.with_suffix(target.suffix + ".part")
    part.unlink(missing_ok=True)
    for attempt in range(1, ATTEMPTS + 1):
        have = part.stat().st_size if part.exists() else 0
        request = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
        try:
            with urllib.request.urlopen(request, timeout=60) as response, part.open("ab") as out:
                while chunk := response.read(CHUNK):
                    out.write(chunk)
            part.replace(target)
            return target.stat().st_size, attempt
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            print(f"   attempt {attempt} failed after {have} bytes: {error}", flush=True)
            if isinstance(error, urllib.error.HTTPError) and error.code in (400, 401, 403):
                break  # expired or invalid signature: retrying cannot help
            time.sleep(2)
    raise RuntimeError(f"download failed after {attempt} attempt(s)")


def check_demo(path: Path) -> tuple[bool, int]:
    """Streams the .dem.zst through zstd: (starts with the CS2 demo magic, decompressed bytes)."""
    total = 0
    magic = b""
    with zstd.open(path, "rb") as demo:
        while chunk := demo.read(CHUNK):
            if not magic:
                magic = chunk[: len(DEMO_MAGIC)]
            total += len(chunk)
    return magic == DEMO_MAGIC, total


def ingest(payload: dict[str, Any], file: str, received_at: float) -> None:
    url = payload["url"]
    record: dict[str, Any] = {
        "file": file,
        "host": urlsplit(url).hostname,
        "seen_at": payload.get("seen_at"),
        "received_at": received_at,
        "url_seconds_left": seconds_left(url, received_at),
    }
    OUT_DIR.mkdir(exist_ok=True)
    target = OUT_DIR / f"{file}.dem.zst"
    start = time.time()
    try:
        record["bytes"], record["attempts"] = download(url, target)
        record["download_s"] = round(time.time() - start, 1)
        record["is_cs2_demo"], record["dem_bytes"] = check_demo(target)
    except (RuntimeError, OSError, zstd.ZstdError) as error:
        record["error"] = str(error)[:300]
    with (OUT_DIR / "ingest.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(record) + "\n")
    print(f"<- {json.dumps(record)}", flush=True)


class Handler(BaseHTTPRequestHandler):
    def _reply(self, status: int, body: dict[str, Any] | None = None) -> None:
        data = json.dumps(body).encode() if body is not None else b""
        self.send_response(status)
        # Lets the extension call us even where it has no host permission (preflighted fetch).
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self._reply(204)

    def do_POST(self) -> None:
        received_at = time.time()
        if self.path != "/ingest/url":
            return self._reply(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(min(length, 64 * 1024)))
            file = validate(payload["url"])
        except (ValueError, KeyError, TypeError):
            return self._reply(400, {"error": "expected JSON with a url"})
        if file is None:
            return self._reply(422, {"error": "not a FACEIT CS2 demo URL"})
        print(f"-> {file} from {urlsplit(payload['url']).hostname}", flush=True)
        threading.Thread(target=ingest, args=(payload, file, received_at), daemon=True).start()
        return self._reply(202, {"accepted": file})

    def log_message(self, format: str, *args: Any) -> None:
        pass  # keep the console to one line per demo


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Listening on http://127.0.0.1:{port}/ingest/url (Ctrl+C to stop)", flush=True)
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()


if __name__ == "__main__":
    main()
