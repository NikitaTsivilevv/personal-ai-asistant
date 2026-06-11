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
