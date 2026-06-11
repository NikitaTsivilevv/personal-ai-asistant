"""Outbound dialing via the Twilio REST API.

The TwiML connects the call's media stream to the worker's public WebSocket,
passing run/task IDs as custom stream parameters so the ws handler can route
the call to the right pipeline.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

import httpx

from ..settings import WorkerSettings


def stream_twiml(settings: WorkerSettings, *, run_id: str, task_id: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response><Connect>"
        f'<Stream url="{escape(settings.public_ws_url)}">'
        f'<Parameter name="run_id" value="{escape(run_id)}" />'
        f'<Parameter name="task_id" value="{escape(task_id)}" />'
        "</Stream></Connect></Response>"
    )


async def start_outbound_call(
    settings: WorkerSettings,
    *,
    to_number: str,
    run_id: str,
    task_id: str,
    status_callback_url: str | None = None,
    http: httpx.AsyncClient | None = None,
) -> str:
    """Create the call; returns the Twilio CallSid."""
    owns_client = http is None
    http = http or httpx.AsyncClient(timeout=30)
    try:
        data = {
            "To": to_number,
            "From": settings.twilio_from_number,
            "Twiml": stream_twiml(settings, run_id=run_id, task_id=task_id),
        }
        if status_callback_url:
            data["StatusCallback"] = status_callback_url
            data["StatusCallbackEvent"] = "initiated ringing answered completed"
        resp = await http.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Calls.json",
            data=data,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        )
        resp.raise_for_status()
        return resp.json()["sid"]
    finally:
        if owns_client:
            await http.aclose()
