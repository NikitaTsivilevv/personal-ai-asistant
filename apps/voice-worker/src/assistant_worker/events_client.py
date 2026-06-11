"""Client for pushing run events to the control plane's internal API.

Shared by the stage-1 simulator and the real call pipeline (EPIC-002):
the event contract is identical (spec requirement).
"""

from __future__ import annotations

import httpx

from assistant_shared.events import RunEvent, RunEventType
from assistant_shared.schemas import RunStatus, Speaker

from .settings import WorkerSettings


class RunClient:
    def __init__(self, http: httpx.AsyncClient, settings: WorkerSettings, run_id: str) -> None:
        self._http = http
        self._settings = settings
        self._run_id = run_id

    async def send(self, event: RunEvent) -> dict:
        resp = await self._http.post(
            f"{self._settings.api_base_url}/internal/runs/{self._run_id}/events",
            json=event.model_dump(mode="json"),
            headers={"X-Internal-Token": self._settings.internal_api_token},
        )
        resp.raise_for_status()
        return resp.json()

    async def status(self, status: RunStatus, *, call_state: str | None = None) -> None:
        data: dict = {"status": status.value}
        if call_state is not None:
            data["call_state"] = call_state
        await self.send(RunEvent(type=RunEventType.status_changed, data=data))

    async def say(self, seq: int, speaker: Speaker, text: str, ts_ms: int | None = None) -> None:
        await self.send(
            RunEvent(
                type=RunEventType.transcript_segment,
                data={
                    "seq": seq,
                    "speaker": speaker.value,
                    "text": text,
                    "ts_ms": ts_ms if ts_ms is not None else seq * 1500,
                },
            )
        )

    async def request_approval(self, kind: str, question: str, context: dict) -> str:
        result = await self.send(
            RunEvent(
                type=RunEventType.approval_requested,
                data={"kind": kind, "question": question, "context": context},
            )
        )
        return result["approval_id"]

    async def completed(self, result_summary: str, estimated_cost_cents: int | None = None, **extra) -> None:
        await self.send(
            RunEvent(
                type=RunEventType.run_completed,
                data={
                    "result_summary": result_summary,
                    "estimated_cost_cents": estimated_cost_cents,
                    **extra,
                },
            )
        )

    async def failed(self, failure_reason: str, **extra) -> None:
        await self.send(
            RunEvent(type=RunEventType.run_failed, data={"failure_reason": failure_reason, **extra})
        )
