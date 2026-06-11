"""Twilio status-callback webhook (EPIC-002 spec §4).

The voice worker owns run-state transitions; this endpoint records telephony
status changes in the audit trail (and is the hook for finer busy/no-answer
routing later).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assistant_db.models import Task, TaskRun
from assistant_shared.schemas import Actor

from ..audit import write_audit
from ..deps import get_session, get_settings
from ..settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def validate_twilio_signature(
    auth_token: str, url: str, params: dict[str, str], signature: str
) -> bool:
    """Standard Twilio HMAC-SHA1 validation (url + sorted form params)."""
    payload = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), signature)


@router.post("/twilio/status")
async def twilio_status(
    request: Request,
    run_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    form = dict((await request.form()).items())

    if not settings.twilio_auth_token.startswith("PLACEHOLDER"):
        signature = request.headers.get("X-Twilio-Signature", "")
        if not validate_twilio_signature(
            settings.twilio_auth_token, str(request.url), form, signature
        ):
            raise HTTPException(status_code=403, detail="invalid twilio signature")

    run = (
        await session.execute(select(TaskRun).where(TaskRun.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    task = (await session.execute(select(Task).where(Task.id == run.task_id))).scalar_one()

    write_audit(
        session,
        user_id=task.user_id,
        actor=Actor.system,
        event_type="telephony.status",
        payload={
            "call_sid": form.get("CallSid"),
            "call_status": form.get("CallStatus"),
            "duration": form.get("CallDuration"),
        },
        task_run_id=run.id,
    )
    await session.commit()
    return {"ok": True}
