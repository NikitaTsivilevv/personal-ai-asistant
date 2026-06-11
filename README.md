# Personal AI Assistant

Personal AI assistant for delegated phone tasks: outbound calls, inbound screening, live control, human approvals, transcripts, summaries, and safe use of personal facts.

Read these first:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `docs/product/personal-ai-assistant-tz.md`
4. The relevant `docs/epics/EPIC-*.md`

## Layout

```text
apps/web            # Next.js: minimal live-call page (stage 1: raw SSE feed stub)
apps/api            # FastAPI: tasks, runs, approvals, run events, SSE
apps/bot            # aiogram Telegram bot: task creation, approvals, summaries
apps/voice-worker   # Stage 1: stub call simulator; EPIC-002: real Pipecat worker
packages/shared     # Pydantic schemas, run-event contract, Redis queue helpers
packages/database   # SQLAlchemy models, Alembic migrations
packages/policy     # Policy engine (autonomy-level rule table)
```

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Node 20+ (web only).

```bash
uv sync --all-packages          # installs Python 3.12 venv + all workspace packages
cp .env.example .env            # fill in real values; sqlite/local-redis defaults work for dev
```

## Run

```bash
uv run assistant-api            # API on http://127.0.0.1:8000 (docs at /docs)
uv run assistant-worker         # worker: WORKER_MODE=simulate (default) | call
uv run assistant-bot            # Telegram bot (needs TELEGRAM_BOT_TOKEN)
cd apps/web && npm install && npm run dev   # live-call page on :3000 (/runs/<run_id>)
```

Real calls (`WORKER_MODE=call`) additionally need `uv sync --all-packages --extra call`
(installs Pipecat), Twilio/Deepgram/Cartesia/LLM keys, and a public wss:// tunnel to the
worker's `/ws` (see `.env.example`).

Migrations (Postgres or sqlite via `DATABASE_URL`):

```bash
cd packages/database && uv run alembic upgrade head
```

## Validate

```bash
uv run pytest -q                # full test suite (sqlite in-memory + fakeredis)
uv run ruff check .             # lint
```
