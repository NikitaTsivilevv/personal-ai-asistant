# HANDOVER 2026-06-11 - Скелет Stage 2 (Outbound Calls)

Продолжение сессии после хендовера по Stage 1. Ветка `feature/stage2-outbound-calls`, PR #2 (стекован на PR #1): https://github.com/NikitaTsivilevv/personal-ai-asistant/pull/2

## Что сделано

- **State machine звонка** (`call/state.py`): dialing → … → ended + ветки failed/no_answer/voicemail/busy; маппинг на stage-1 RunStatus, контракт событий не менялся (`call_state` едет внутри data).
- **Ядро агента** (`call/agent.py`): сборка системного промпта (цель, ограничения, allowed facts, policy-преамбула), языки ES/EN/RU; **AI-disclosure — захардкоженная первая TTS-фраза**, не управляется промптом.
- **Инструменты через policy** (`call/tools.py`): request_approval/end_call/log_fact/propose_summary; `ControlRouter` (`call/control.py`) — единственный потребитель control-списка, маршрутизирует approve/whisper/hangup во время звонка.
- **Pipecat 1.3 пайплайн** (`call/pipeline.py`): Twilio media stream ↔ Deepgram ↔ OpenAI-совместимый LLM (swappable) ↔ Cartesia. ВАЖНО: pipecat 1.3 удалил `TranscriptProcessor` — транскрипт и TTFB-метрики собираются кастомным frame-observer'ом. Импорты и сигнатуры проверены против установленного pipecat 1.3.0 (extra `call`).
- **Дозвон**: Twilio REST + TwiML Stream с run_id/task_id (`call/twilio_client.py`); ws-сервер воркера (`call/server.py`); `WORKER_MODE=simulate|call`.
- **Устойчивость**: retry/backoff для busy/no-answer (`call/retry.py`); свипер зависших ранов в API (`sweeper.py`, протестирован); пер-turn метрики в payload финального события.
- **API**: вебхук Twilio status (с валидацией подписи), `POST /runs/{id}/hangup|whisper`, CORS.
- **Live-страница** (`apps/web/app/runs/[id]`): транскрипт по SSE, статус, Hang up, Whisper. `next build` чистый.
- Тесты: 59 (все зелёные), ruff чистый.

## Известные TODO (живая сессия с провайдерами)

- busy vs no-answer сейчас не различаются: воркер таймаутится в no_answer; маршрутизацию из Twilio-колбэков доделать при живом тесте.
- Прогнать пайплайн с реальным звуком (фразы A2-A3 плана), затем D1 — реальная бронь ресторана.
- profile_facts из БД в промпт агента — придёт с EPIC-005 (структура готова: `ProfileFactView`).

## Следующие шаги

См. PROJECT_CONTEXT.md: смержить PR #1 → PR #2, регистрации сервисов, live-проверка stage 1, потом stage 2 phase A.
