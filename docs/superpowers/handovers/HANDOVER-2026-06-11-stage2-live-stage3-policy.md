# HANDOVER 2026-06-11 - Live-проверка Stage 2 + Policy Engine (Stage 3 A/B/C1)

Третья сессия за день. Все ключи сервисов заполнены, всё проверялось вживую.

## Где остановились

`main` содержит PR #1-#5. Достигнута граница, дальше которой нужны живые звонки с участием Никиты.

- **Stage 1**: серверная e2e-проверка на реальных Postgres + Upstash прошла (очередь → симулятор → пауза approval → resolve → done). Проверка с телефона (Telegram `/new`, кнопки) — отложена Никитой, не сделана.
- **Stage 2 (EPIC-002)**: hello-world звонок состоялся на номер владельца (+34653753061): Twilio → Cloudflare quick tunnel → Pipecat → Deepgram/Cartesia/gpt-4o-mini, RU-disclosure первой фразой, транскрипт и LLM-резюме доехали, Cartesia TTFB 0.17s. Осталась фаза D (реальная бронь).
- **Stage 3 (EPIC-003)**: фазы A, B1, B2, C1 реализованы и смержены (PR #3, #4, #5). Осталось: C2 Transfer-to-me, C3 Take-over, D живые сценарии.

## Что изменилось

- **Цены (задача A1 stage-2)**: `docs/research/2026-06-11-provider-pricing.md` — ~$0.04/мин городской ES, в конверте D-5, модели не менялись. Open-questions обновлён.
- **Policy engine v1** (D-10): таксономия и схема правил в `assistant_shared/policy.py`; JSON-профили per-scenario в `assistant_policy/rules/`; жёсткий пол в коде (payment/terms/sensitive никогда не `allow`); decision несёт rule_id + хеш входов; событие `policy_decision` → audit_log с actor=policy.
- **Approval expiry**: 120с по умолчанию; событие `approval_expired` помечает строку expired, ран продолжается, агент мягко завершает разговор.
- **Profile facts (B2)**: колонка `allowed_scenarios` (миграция b3c41f09d2e7, применена к живой БД); `/facts` CRUD API (audited, значения фактов в audit не пишутся); воркер грузит факты сценарно и единообразно в промпт и policy-контекст; команды бота `/facts`, `/fact_add`, `/fact_del`.
- **Pause automation (C1)**: `POST /runs/{id}/pause|resume` → ControlRouter → PauseGate (глушит LLM-триггеры, транскрипт идёт); кнопка на live-странице.
- **Фиксы**: `create_ws_app` не возвращал app (все запросы 500-или — найдено при первом живом запуске); обработка Upstash BRPOP TimeoutError; тестовые фикстуры изолированы от девелоперского `.env` (реальный TWILIO_AUTH_TOKEN включал валидацию подписи и ронял тесты).

## Валидация

- `uv run pytest -q` — 81 passed (включая полную матрицу policy).
- `uv run ruff check .` — чисто. `next build` — чисто.
- Alembic: head = b3c41f09d2e7 на живой БД; up/down/up проверены на sqlite.
- Живой звонок: run completed, резюме в Telegram.

## Оперативное состояние (хрупкое, проверить при старте!)

- api/bot/worker запускались в фоне сессии Claude — после перезагрузки их надо поднять заново.
- `.env` `DATABASE_URL` всё ещё `postgresql://...` — работает только потому, что процессы стартуют с переопределённой переменной `postgresql+asyncpg://`. **Починить руками в `.env`.**
- Cloudflared quick tunnel (`phase-bringing-comparison-katrina.trycloudflare.com` → localhost:8765): URL умирает с процессом cloudflared; при новом запуске обновить `PUBLIC_WS_URL` в `.env`.
- Воркер для звонков: `WORKER_MODE=call` (в `.env` стоит simulate, переопределяется при запуске).

## Решения

- **D-10** — policy engine v1: rules-as-data, hard floor в коде, сценарные профили, audit с rule id, expiry 120s.

## Открытые вопросы / риски

- Закрыты: цены моделей; per-scenario правила (теперь данные); поведение при ожидании approval (филлер + expiry).
- Pause/whisper/expiry проверены тестами, но не на живом звонке.
- busy vs no-answer по-прежнему не различаются (TODO живой сессии).

## Следующие шаги (= начало следующей сессии)

1. Подготовка стенда: поправить `DATABASE_URL` в `.env`; поднять cloudflared (обновить `PUBLIC_WS_URL`), api, bot, worker (call); набить факты через `/fact_add`.
2. Stage-1 приёмка с телефона: `/new`, Approve-прогон, Reject-прогон, пуш итога, live-страница.
3. EPIC-003 D: живые сценарные звонки на свой номер (doctor — approval на данные; insurance — deny отмены; restaurant — без approvals на L1; expiry — не отвечать на approval 2 минуты; pause/resume и whisper с live-страницы).
4. EPIC-002 D1: реальная бронь ресторана, транскрипт и заметки в `docs/research/`.
5. EPIC-003 C2/C3: Transfer-to-me (Twilio-мост), Take-over (WebRTC) — проектировать и тестировать вживую.

## Что читать в новой сессии

`AGENTS.md` → `PROJECT_CONTEXT.md` → `DECISIONS.md` (D-9, D-10) → этот хендовер → планы stage-2/stage-3 в `docs/superpowers/plans/`.
