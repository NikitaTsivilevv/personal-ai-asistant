"""Thin async client for the control-plane API."""

from __future__ import annotations

import httpx

from assistant_shared.schemas import StructuredGoal

from .settings import BotSettings


class ApiClient:
    def __init__(self, settings: BotSettings, http: httpx.AsyncClient | None = None) -> None:
        self._base = settings.api_base_url.rstrip("/")
        self._http = http or httpx.AsyncClient(timeout=30)

    async def create_task(
        self,
        *,
        title: str,
        instructions: str,
        structured_goal: StructuredGoal,
        target_phone: str | None,
        target_name: str | None,
    ) -> dict:
        resp = await self._http.post(
            f"{self._base}/tasks",
            json={
                "title": title,
                "instructions": instructions,
                "structured_goal": structured_goal.model_dump(),
                "target_phone": target_phone,
                "target_name": target_name,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def list_tasks(self) -> list[dict]:
        resp = await self._http.get(f"{self._base}/tasks")
        resp.raise_for_status()
        return resp.json()

    async def queue_task(self, task_id: str) -> dict:
        resp = await self._http.post(f"{self._base}/tasks/{task_id}/queue")
        resp.raise_for_status()
        return resp.json()

    async def resolve_approval(self, approval_id: str, decision: str) -> dict:
        resp = await self._http.post(
            f"{self._base}/approvals/{approval_id}/resolve",
            json={"decision": decision, "resolved_via": "telegram"},
        )
        resp.raise_for_status()
        return resp.json()

    async def list_facts(self) -> list[dict]:
        resp = await self._http.get(f"{self._base}/facts")
        resp.raise_for_status()
        return resp.json()

    async def upsert_fact(
        self,
        *,
        key: str,
        value: str,
        sensitivity: str = "medium",
        allowed_by_default: bool = False,
        allowed_scenarios: list[str] | None = None,
    ) -> dict:
        resp = await self._http.post(
            f"{self._base}/facts",
            json={
                "key": key,
                "value": value,
                "sensitivity": sensitivity,
                "allowed_by_default": allowed_by_default,
                "allowed_scenarios": allowed_scenarios or [],
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_fact(self, key: str) -> None:
        resp = await self._http.delete(f"{self._base}/facts/{key}")
        resp.raise_for_status()

    async def aclose(self) -> None:
        await self._http.aclose()
