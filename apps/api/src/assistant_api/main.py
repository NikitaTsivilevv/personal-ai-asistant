"""FastAPI app factory and entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from assistant_db.models import Base
from assistant_db.session import create_engine, create_session_factory
from assistant_shared.queue import create_redis

from .routers import approvals, runs, tasks, webhooks
from .settings import Settings
from .sweeper import sweeper_loop


def create_app(
    settings: Settings | None = None,
    *,
    engine: AsyncEngine | None = None,
    redis: aioredis.Redis | None = None,
    create_schema: bool = False,
) -> FastAPI:
    """Build the app. Tests inject sqlite engine / fakeredis and create_schema=True;
    real deployments rely on Alembic migrations instead."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.engine = engine or create_engine(settings.database_url, echo=settings.echo_sql)
        app.state.session_factory = create_session_factory(app.state.engine)
        app.state.redis = redis if redis is not None else create_redis(settings.redis_url)
        if create_schema:
            async with app.state.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        sweeper_task = None
        if settings.stale_run_timeout_s > 0:
            import asyncio

            sweeper_task = asyncio.create_task(
                sweeper_loop(
                    app.state.session_factory,
                    app.state.redis,
                    stale_after_s=settings.stale_run_timeout_s,
                    interval_s=settings.stale_run_sweep_interval_s,
                )
            )
        yield
        if sweeper_task is not None:
            sweeper_task.cancel()
        await app.state.redis.aclose()
        await app.state.engine.dispose()

    app = FastAPI(title="Personal AI Assistant - Control Plane API", lifespan=lifespan)
    if settings.cors_origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(tasks.router)
    app.include_router(approvals.router)
    app.include_router(runs.router)
    app.include_router(webhooks.router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


def run() -> None:
    import uvicorn

    settings = Settings()
    uvicorn.run(create_app(settings), host=settings.api_host, port=settings.api_port)
