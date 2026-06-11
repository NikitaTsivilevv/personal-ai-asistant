from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    api_base_url: str = "http://127.0.0.1:8000"
    internal_api_token: str = "dev-internal-token"

    # How long one simulated run waits for an approval before giving up (seconds).
    approval_timeout_s: int = 600
    # Artificial pacing between simulated events (seconds); 0 in tests.
    step_delay_s: float = 1.0
