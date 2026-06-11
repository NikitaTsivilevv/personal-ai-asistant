from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    telegram_bot_token: str = "PLACEHOLDER_TELEGRAM_BOT_TOKEN"
    # Comma-separated Telegram user IDs allowed to use the bot (auth allowlist).
    telegram_allowed_user_ids: str = ""

    api_base_url: str = "http://127.0.0.1:8000"
    redis_url: str = "redis://localhost:6379/0"

    # LLM for /new normalization; empty key -> heuristic fallback (plan D2 note).
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    @property
    def allowed_ids(self) -> set[int]:
        return {int(x) for x in self.telegram_allowed_user_ids.split(",") if x.strip()}
