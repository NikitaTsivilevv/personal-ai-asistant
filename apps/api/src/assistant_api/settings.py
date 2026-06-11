"""API configuration. All values come from env / .env (see .env.example)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    # Postgres in real deployments (Neon/Supabase); sqlite for quick local runs.
    database_url: str = "sqlite+aiosqlite:///./dev.db"
    redis_url: str = "redis://localhost:6379/0"

    # Worker-facing internal API auth.
    internal_api_token: str = "dev-internal-token"

    # Single-user MVP bootstrap (D-7: still user_id everywhere).
    default_user_name: str = "Owner"
    default_user_locale: str = "ru"
    telegram_owner_user_id: int | None = None

    api_host: str = "127.0.0.1"
    api_port: int = 8000

    echo_sql: bool = False

    # Comma-separated origins for the web live-call page.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Twilio webhook signature validation; skipped while PLACEHOLDER (dev).
    twilio_auth_token: str = "PLACEHOLDER"

    # Crash recovery (EPIC-002 spec, acceptance criterion 5): runs with no
    # events for this long are marked failed. 0 = sweeper disabled (tests).
    stale_run_timeout_s: int = 0
    stale_run_sweep_interval_s: int = 60
