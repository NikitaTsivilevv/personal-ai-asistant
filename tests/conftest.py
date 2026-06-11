"""Test fixtures: in-memory sqlite, fakeredis, ASGI-transport API client."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fakeredis import aioredis as fakeaioredis
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from assistant_api.main import create_app
from assistant_api.settings import Settings


@pytest.fixture
def fake_redis() -> fakeaioredis.FakeRedis:
    return fakeaioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,  # tests must not depend on the developer's .env
        database_url="sqlite+aiosqlite://",
        internal_api_token="test-internal-token",
        default_user_name="Test Owner",
        twilio_auth_token="PLACEHOLDER",
    )


@pytest.fixture
async def app(settings: Settings, fake_redis: fakeaioredis.FakeRedis):
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    application = create_app(settings, engine=engine, redis=fake_redis, create_schema=True)
    async with LifespanManager(application):
        yield application


@pytest.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def internal_headers() -> dict:
    return {"X-Internal-Token": "test-internal-token"}


TASK_PAYLOAD = {
    "title": "Записаться к стоматологу",
    "instructions": "Запиши меня к стоматологу на этой неделе, лучше после 17:00",
    "structured_goal": {
        "objective": "Записаться к стоматологу на этой неделе после 17:00",
        "constraints": ["после 17:00", "на этой неделе"],
        "allowed_facts": ["имя", "телефон"],
        "autonomy_level": 1,
    },
    "target_phone": "+34911222333",
    "target_name": "Клиника Дента",
}


@pytest.fixture
def task_payload() -> dict:
    return dict(TASK_PAYLOAD)
