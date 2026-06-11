# HANDOVER 2026-06-11 - Реализация Stage 1 (Control Plane)

## Где остановились

EPIC-001 реализован целиком на ветке `feature/stage1-control-plane`, открыт PR #1:
https://github.com/NikitaTsivilevv/personal-ai-asistant/pull/1

Репозиторий: https://github.com/NikitaTsivilevv/personal-ai-asistant (доки в `main`, код в PR).

Не сделано только то, что требует регистраций в сервисах: живая проверка бота с телефона и провижининг Neon/Upstash. Все ключи — плейсхолдеры в `.env.example`.

## Что изменилось

- Скаффолд монорепы: uv workspace (Python 3.12), `apps/api|bot|voice-worker|web`, `packages/shared|database|policy`.
- Схема v1 (8 таблиц по спеке §3) + Alembic-миграция, проверена up/down.
- FastAPI: `POST/GET /tasks`, queue/cancel, `POST /approvals/{id}/resolve`, `POST /internal/runs/{id}/events` (токен-аутентификация воркера), `GET /runs/{id}/events` (SSE), `/health`. Каждый переход пишет `audit_log`.
- Redis-механика (контракты в `assistant_shared`): очередь `queue:task_runs` (list), контрольный список `run:{id}:control` (разблокировка воркера после approve/reject/cancel), pub/sub `events:runs` (SSE + бот).
- Stub-воркер: симулирует звонок (running → транскрипт → policy-проверка → approval-пауза → completed/failed).
- Policy-стаб: `evaluate()` по таблице autonomy_level 0-3; платежи/изменение договора всегда требуют подтверждения.
- Telegram-бот (aiogram): `/new` (LLM-нормализация с эвристическим фолбэком без ключа), `/tasks`, инлайн-кнопки Approve/Reject, пуш итогов.
- Web-стаб: Next.js страница `/runs/[id]` с сырым SSE-фидом.
- Тесты: 26 штук (sqlite in-memory + fakeredis), включая e2e queue→worker→approval→done в обоих исходах. ruff чистый.

## Решения

- **D-9** — uv workspace; отдельный `apps/bot`; Redis lists + pub/sub; тесты на sqlite/fakeredis. (См. DECISIONS.md.)

## Обновлённые доки

- `README.md` — инструкции запуска/валидации.
- `AGENTS.md` — фактический layout + команды валидации.
- `PROJECT_CONTEXT.md` — статус и шаги резюма.
- `docs/epics/EPIC-001-control-plane.md` — статус.
- `docs/superpowers/plans/2026-06-11-mvp-stage1-control-plane-plan.md` — чекбоксы и оговорки.

## Валидация

- `uv run pytest -q` — 26 passed.
- `uv run ruff check .` — чисто.
- Alembic up/down/up на временной sqlite — ок.
- uvicorn стартует, `GET /health` → ok.
- НЕ проверено вживую: Telegram-флоу с телефона, LLM-нормализация с реальным ключом, Postgres/Upstash.

## Открытые вопросы / риски

- Без изменений (см. open-questions.md). Нестойкость очереди (Redis list) зафиксирована как осознанный трейд-офф в D-9, пересмотр в EPIC-006.

## Следующие шаги

1. Зарегистрировать: бот у @BotFather, Neon/Supabase, Upstash, ключ Anthropic; заполнить `.env`.
2. Запустить api+worker+bot, прогнать приёмочные критерии 1-4 EPIC-001 с телефона.
3. Смержить PR #1.
4. Перед EPIC-002 перепроверить цены Deepgram/Cartesia/LLM (open-questions.md).

## Что читать в новой сессии

`AGENTS.md` → `PROJECT_CONTEXT.md` → `DECISIONS.md` (D-9) → `docs/epics/EPIC-002-outbound-calls.md` + его спека/план.
