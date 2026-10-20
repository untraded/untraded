# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""👍/👎 on a priority (vision § 6.3): what the rules learn from."""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from untraded_api.deps import ConnDep, UserDep

router = APIRouter(prefix="/advice", tags=["advice"])


class Vote(BaseModel):
    vote: Literal[-1, 0, 1]
    """1 for 👍, -1 for 👎, 0 to take the vote back."""


@router.post("/{advice_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def give_feedback(advice_id: uuid.UUID, body: Vote, conn: ConnDep, user: UserDep) -> None:
    # Row-level security: the advice must belong to one of the user's workspaces, and the vote
    # can only be the user's own.
    if conn.execute("SELECT 1 FROM advice WHERE id = %s", (advice_id,)).fetchone() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such advice")
    if body.vote == 0:
        conn.execute(
            "DELETE FROM advice_feedback WHERE advice_id = %s AND user_id = %s", (advice_id, user)
        )
        return
    conn.execute(
        """
        INSERT INTO advice_feedback (advice_id, user_id, vote) VALUES (%s, %s, %s)
        ON CONFLICT (advice_id, user_id) DO UPDATE SET vote = EXCLUDED.vote, created_at = now()
        """,
        (advice_id, user, body.vote),
    )
