"""FastAPI dependencies: db session, redis, default user, internal auth."""

from __future__ import annotations

from collections.abc import AsyncIterator

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assistant_db.models import User

from .settings import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_redis(request: Request) -> aioredis.Redis:
    return request.app.state.redis


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


async def get_default_user(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> User:
    """Single-user MVP: every request acts on behalf of the bootstrap user."""
    user = (await session.execute(select(User).limit(1))).scalar_one_or_none()
    if user is None:
        user = User(
            display_name=settings.default_user_name,
            locale=settings.default_user_locale,
            telegram_user_id=settings.telegram_owner_user_id,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def require_internal_token(
    settings: Settings = Depends(get_settings),
    x_internal_token: str = Header(default=""),
) -> None:
    if x_internal_token != settings.internal_api_token:
        raise HTTPException(status_code=401, detail="invalid internal token")
