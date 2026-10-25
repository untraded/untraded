# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Demos a player sends from the site: FACEIT, ESEA, scrims, or a Premier match the collector
missed.

`POST /uploads` takes the file as the raw request body (`?name=` its file name, `mode`, the
time it was played), streamed to the uploads directory, never held in memory: a FACEIT demo
weighs up to 300 MB. Everything that can refuse it cheaply is checked before the body is read
(consent, limits, name, size, free disk). The worker then checks the demo itself
(`ingest_upload`) and parses it; `GET /uploads` follows what became of each upload.

Refusals are `{"reason": code}`, codes the site translates: `not_a_demo`, `too_large`,
`disk_full`, `consent`, `quota`, `busy`, and, once received, `corrupt`, `unsupported_mode`,
`not_a_player`, `parse_failed`.
"""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import datetime as dt
import shutil
import uuid
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from untraded_api.db import Database
from untraded_api.deps import ConnDep, DatabaseDep, SettingsDep, UserDep
from untraded_api.settings import Settings

router = APIRouter(prefix="/uploads", tags=["uploads"])

# The demo files the worker reads (`untraded.demofile.SUFFIXES`), longest suffix first, and what
# each starts with: a file that does not is refused before it is stored.
MAGIC = {
    ".dem.bz2": b"BZh",
    ".dem.gz": b"\x1f\x8b",
    ".dem.zst": b"\x28\xb5\x2f\xfd",
    ".dem": b"PBDEMS2\x00",
}
LIMIT_STATUS = {
    "consent": status.HTTP_409_CONFLICT,
    "quota": status.HTTP_429_TOO_MANY_REQUESTS,
    "busy": status.HTTP_429_TOO_MANY_REQUESTS,
}
KEPT_DAYS = 30
"""How far back `GET /uploads` looks."""


class Refused(HTTPException):
    def __init__(self, status_code: int, reason: str) -> None:
        super().__init__(status_code, {"reason": reason})


class UploadOut(BaseModel):
    upload_id: uuid.UUID
    """Also the match it becomes, unless the demo was already known (see `GET /uploads`)."""


class UploadLine(BaseModel):
    upload_id: uuid.UUID
    match_id: uuid.UUID
    """The match the demo became: open it once `state` is `ready`."""
    received_at: dt.datetime
    mode: str
    map: str | None
    played_at: dt.datetime | None
    state: Literal["processing", "ready", "refused", "failed"]
    reason: str | None
    """Why it was refused or failed, as a code (see the module)."""


class UploadList(BaseModel):
    items: list[UploadLine]
    refusal: str | None
    """Why a demo sent now would be refused (`off`, `disk_full`, `consent`, `quota`, `busy`), or
    null: the site says so before sending hundreds of megabytes the API would not read."""
    max_bytes: int
    """The largest file the player may send: the site checks it first too."""


def _refusal(db: Database, user: uuid.UUID, settings: Settings) -> str | None:
    with db.transaction(user) as conn:
        row = conn.execute(
            "SELECT my_upload_refusal(%s, %s)",
            (settings.uploads_per_day, settings.uploads_in_flight),
        ).fetchone()
    return str(row[0]) if row and row[0] is not None else None


def _record(
    db: Database,
    user: uuid.UUID,
    settings: Settings,
    upload: uuid.UUID,
    file: str,
    mode: str,
    played_at: dt.datetime,
) -> str | None:
    with db.transaction(user) as conn:
        row = conn.execute(
            "SELECT add_my_upload(%s, %s, %s::match_mode, %s, %s, %s)",
            (
                upload,
                file,
                mode,
                played_at,
                settings.uploads_per_day,
                settings.uploads_in_flight,
            ),
        ).fetchone()
    return str(row[0]) if row and row[0] is not None else None


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def send_demo(
    request: Request,
    db: DatabaseDep,
    user: UserDep,
    settings: SettingsDep,
    name: Annotated[str, Query(min_length=5, max_length=255)],
    mode: Literal["faceit", "esea", "scrim"],
    played_at: dt.datetime,
) -> UploadOut:
    """Receives a demo. `mode` is what the player says it is; a demo from Valve's servers is
    recognised by the worker whatever the player chose (Premier, or refused)."""
    if settings.uploads_dir is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "uploads are off here")
    suffix = next((s for s in MAGIC if name.lower().endswith(s)), None)
    if suffix is None:
        raise Refused(status.HTTP_422_UNPROCESSABLE_CONTENT, "not_a_demo")
    if played_at.tzinfo is None or played_at > dt.datetime.now(dt.UTC) + dt.timedelta(days=1):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": "played_at"})
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > settings.upload_max_bytes:
        raise Refused(status.HTTP_413_CONTENT_TOO_LARGE, "too_large")
    if _disk_full(settings.uploads_dir, settings):
        raise Refused(status.HTTP_507_INSUFFICIENT_STORAGE, "disk_full")
    folder = Path(settings.uploads_dir)
    refusal = await run_in_threadpool(_refusal, db, user, settings)
    if refusal is not None:
        raise Refused(LIMIT_STATUS[refusal], refusal)

    upload = uuid.uuid4()
    target = folder / f"{upload}{suffix}"
    partial = target.with_name(target.name + ".part")
    try:
        await _receive(request, partial, MAGIC[suffix], settings.upload_max_bytes)
        partial.replace(target)
        refusal = await run_in_threadpool(
            _record, db, user, settings, upload, target.name, mode, played_at
        )
    except BaseException:
        partial.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise
    if refusal is not None:  # another upload took the last place meanwhile
        target.unlink(missing_ok=True)
        raise Refused(LIMIT_STATUS[refusal], refusal)
    return UploadOut(upload_id=upload)


async def _receive(request: Request, partial: Path, magic: bytes, limit: int) -> None:
    """Writes the body to `partial`, refusing it as soon as it is too large or does not start
    like the file its name says."""
    size = 0
    head = b""
    with partial.open("wb") as file:
        try:
            async for chunk in request.stream():
                if len(head) < len(magic):
                    head += chunk[: len(magic) - len(head)]
                    if not magic.startswith(head) and not head.startswith(magic):
                        raise Refused(status.HTTP_422_UNPROCESSABLE_CONTENT, "not_a_demo")
                size += len(chunk)
                if size > limit:
                    raise Refused(status.HTTP_413_CONTENT_TOO_LARGE, "too_large")
                await run_in_threadpool(file.write, chunk)
        except ClientDisconnect:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "upload interrupted") from None
    if len(head) < len(magic):
        raise Refused(status.HTTP_422_UNPROCESSABLE_CONTENT, "not_a_demo")


def _line(row: tuple[Any, ...]) -> UploadLine:
    upload_id, match_id, received_at, mode, match_status, rejected, map_name, played_at = row
    state: Literal["processing", "ready", "refused", "failed"]
    reason = rejected
    if rejected is not None:
        state = "refused"
    elif match_status == "ready":
        state = "ready"
    elif match_status == "failed":
        state, reason = "failed", "parse_failed"
    elif match_status == "unavailable":
        state, reason = "refused", "unsupported_mode"
    else:
        state = "processing"
    return UploadLine(
        upload_id=upload_id,
        match_id=match_id,
        received_at=received_at,
        mode=mode,
        map=map_name,
        played_at=played_at,
        state=state,
        reason=reason,
    )


@router.get("")
def list_uploads(conn: ConnDep, settings: SettingsDep) -> UploadList:
    """The player's uploads of the last 30 days, newest first, and whether they may send one."""
    rows = conn.execute("SELECT * FROM my_uploads(%s)", (KEPT_DAYS,)).fetchall()
    refusal: str | None
    if settings.uploads_dir is None:
        refusal = "off"
    elif _disk_full(settings.uploads_dir, settings):
        refusal = "disk_full"
    else:
        row = conn.execute(
            "SELECT my_upload_refusal(%s, %s)",
            (settings.uploads_per_day, settings.uploads_in_flight),
        ).fetchone()
        refusal = str(row[0]) if row and row[0] is not None else None
    return UploadList(
        items=[_line(tuple(row)) for row in rows],
        refusal=refusal,
        max_bytes=settings.upload_max_bytes,
    )


def _disk_full(uploads_dir: str, settings: Settings) -> bool:
    folder = Path(uploads_dir)
    folder.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(folder).free < settings.upload_min_free_bytes
