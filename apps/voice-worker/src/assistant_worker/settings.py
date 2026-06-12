from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    api_base_url: str = "http://127.0.0.1:8000"
    internal_api_token: str = "dev-internal-token"

    # How long a run waits for an in-call approval before it expires and the
    # agent wraps up gracefully (EPIC-003 spec: default 2 min).
    approval_timeout_s: int = 120
    # Artificial pacing between simulated events (seconds); 0 in tests.
    step_delay_s: float = 1.0

    # "simulate" = stage-1 stub lifecycle; "call" = real Twilio/Pipecat call.
    worker_mode: str = "simulate"

    # --- Telephony (EPIC-002) ---
    twilio_account_sid: str = "PLACEHOLDER"
    twilio_auth_token: str = "PLACEHOLDER"
    twilio_from_number: str = "PLACEHOLDER"  # the assistant's own Spanish number
    # Public wss:// URL Twilio connects the media stream to (Cloudflare Tunnel in dev).
    public_ws_url: str = "wss://PLACEHOLDER_HOST/ws"
    # Local server the worker runs to accept that stream.
    ws_host: str = "0.0.0.0"
    ws_port: int = 8765

    # --- Voice pipeline providers ---
    deepgram_api_key: str = "PLACEHOLDER"
    cartesia_api_key: str = "PLACEHOLDER"
    cartesia_voice_id: str = "PLACEHOLDER"  # pick an ES-capable voice during provisioning
    # Swappable conversation LLM (D-5): any OpenAI-compatible endpoint.
    llm_api_key: str = "PLACEHOLDER"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""  # empty = api.openai.com

    # Summary/normalization LLM.
    anthropic_api_key: str = ""

    # Retry policy for busy/no-answer.
    retry_max_attempts: int = 3
    retry_base_delay_s: float = 120.0

    # Deterministic call-termination backstop: a call is force-ended after this
    # wall-clock duration or this many conversation turns, even if the LLM never
    # calls end_call (prevents runs hung in 'running').
    max_call_duration_s: int = 360
    max_call_turns: int = 16
