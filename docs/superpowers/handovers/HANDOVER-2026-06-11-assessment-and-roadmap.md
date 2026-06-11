# HANDOVER 2026-06-11 — Качество звонка добито в коде, оценка проекта, дорожная карта

Пятая сессия за день. Доделали два бага качества из прошлой сессии (PR #7), прогнали офлайн
A/B, разобрались, почему «молчал» Telegram-бот, и провели оценку состояния проекта с
дорожной картой (D-12). Телефона на момент закрытия нет — живые шаги отложены.

## Где остановились

`main` содержит PR #1–#8. Оба блокирующих бага качества разговора **исправлены в коде
(PR #7), ждут живой валидации**. Стек (api+bot) поднят в фоне текущей сессии после того, как
был найден мёртвым. Дальше — офлайн-работа по D-12 (живой звонок не нужен).

## Что сделано в этой сессии

1. **PR #6** (`feature/stage2-night-resilience` → main): закоммичено проверенное ночное дерево
   (queue ConnectionError resilience, `InboundAudioProbe`, prompt role/sensitive фиксы) + дизайн/план/handover доки; `.cloudflared-session.log` в gitignore.
2. **PR #7** (`feature/stage2-call-quality` → main): два фикса качества (см. ниже). Прошёл полный
   subagent-driven цикл: implementer + spec-review + code-quality-review на каждую задачу + финальное ревью.
3. **PR #8** (`docs/d11-ab-results` → main): запись A/B в D-11; `*-session.log` в gitignore.
4. **Bot debugging:** root cause — процессы api+bot не были запущены (не баг кода). Поднял оба,
   подтвердил по логам, что бот обрабатывает команды (`Update … is handled`, `/tasks` → 200).
5. **Оценка проекта + дорожная карта (D-12).**

### Фикс 1 — turn-детекция (pipecat 1.3)
Корень: `vad_analyzer=SileroVADAnalyzer()` передавался в `FastAPIWebsocketParams`, но в pipecat
1.3 у `TransportParams` нет такого поля и pydantic его молча игнорировал — VAD не подключался
вообще, ходы не закрывались. Фикс: `build_vad_analyzer()` (`VADParams(stop_secs=0.3, …)`) и
`build_turn_analyzer()` (`LocalSmartTurnAnalyzerV3` с VAD-only fallback) в `pipeline.py`,
подключены на user-aggregator (`LLMUserAggregatorParams` + `UserTurnStrategies`); barge-in включён по умолчанию.

### Фикс 2 — дрейф роли
Language-aware `ROLE_FEWSHOT` в `agent.py` (иллюстративное имя, не реальный юзер — D-7; стоит
перед whisper-блоком). Офлайн-харнесс `scripts/eval_role_drift.py` мерит дрейф через реальный
LLM без телефона.

### A/B результат (D-11 follow-up)
`eval_role_drift.py`, 3 прогона/модель, имя-проба `Carlos Ruiz` (нет в few-shot, чтобы исключить
эхо): **haiku и sonnet держат роль 3/3**, называют реальный факт. Вывод: few-shot достаточно,
**остаёмся на claude-haiku-4-5**. Оговорка: харнесс tool-free и single-turn — живое подтверждение нужно.

## Оценка проекта (для следующей сессии)

**Сильное:** policy-движок как ядро-дифференциатор (rules-as-data, code hard-floor, autonomy 0–3,
аудит rule-id+hash); compliance-примитивы (неотменяемый дисклоуз, approval-гейты, audit);
чистая архитектура; дисциплина тестов; зерно eval-культуры.

**Главные пробелы (по приоритету боли):**
1. **Надёжность стенда** — нет супервизии; api+bot падают молча (хит этой сессии). №1 блокер «реального использования».
2. **Сценарии построены, но не подключены к интейку** — `normalize.py` не извлекает `scenario`,
   `confirm_task` его не передаёт → `structured_goal.scenario` всегда `generic`, профили
   doctor/insurance/restaurant и сценарные факты мертвы. (Это и есть ответ на «заточено под клинику»:
   не заточено — наоборот, вся сценарность не активируется; перекос только в booking-лексике few-shot.)
3. **Eval почти нет** — один офлайн-пробник; изменения промпта/модели/сценариев делаются вслепую.
4. **Few-shot перекошен в booking** — обобщить/сценаризовать.
5. **Turn-детекция/STT под испанские колл-центры** — починено в коде, не валидировано вживую.

**Best practices (как НАДО):** eval-driven development с LLM-симулятором собеседника по
сценариям (успех задачи + корректность policy + удержание роли + latency + cost), сценарные
плейбуки, слоистые guardrails + PII-редакция, бюджеты latency, супервизия процессов, трейс звонка.

## Решения добавлены

- **D-11 follow-up** — A/B: остаёмся на haiku.
- **D-12** — следующий workstream: eval-driven development, подключение сценариев к интейку,
  надёжность раньше масштабирования. Офлайн-работа впереди телефонной.

## Доки обновлены

`DECISIONS.md` (D-11 follow-up, D-12), `PROJECT_CONTEXT.md` (статус + next steps),
`docs/epics/EPIC-002` (баги фикснуты в коде), `EPIC-003` (сценарии dormant),
`docs/product/open-questions.md` (+раздел Evaluation/Scenario Routing),
`docs/product/risks.md` (turn/role → Mitigated; +scenario-dormant; stand-fragility обновлён),
`.gitignore` (`*-session.log`).

## Валидация

`uv run pytest -q` → 90 passed; `uv run ruff check .` → clean. A/B прогнан на реальных моделях.
Бот подтверждённо обрабатывает команды (логи).

## Риски / открытые вопросы

См. обновлённые `risks.md` и `open-questions.md`. Ключевое: надёжность стенда (open, повторный
хит), сценарии не подключены (open), как детектить сценарий в интейке, насколько верным должен
быть симулятор собеседника в eval.

## Следующие шаги (= начало следующей сессии, всё офлайн)

1. Подключить сценарий к интейку (`normalize` → `scenario`, `confirm_task` передаёт).
2. Eval-харнесс с симулятором собеседника по 5 сценариям (обобщение `eval_role_drift`).
3. Надёжность api/bot (супервизия + reconnect); план ухода с quick-tunnel.
4. Обобщить/сценаризовать few-shot.
5. (нужен телефон) живая валидация turn-детекции + роли; затем EPIC-003 D, EPIC-002 D1, C2/C3.

Рекомендация: начать с №2 (eval-харнесс) или связки №1+№2 — без eval всё остальное вслепую.
Пройти через brainstorming → спеку → план перед кодом.

## Операционные заметки

- Запуск: `uv run assistant-api`, `uv run assistant-bot`, `uv run assistant-worker`.
- ⚠️ Только ОДИН `assistant-bot` одновременно (иначе Telegram 409 → «бот не реагирует»).
- Если api/bot подняты в фоне прошлой сессии — проверь процессы перед запуском новых.
- `.env`: `LLM_BASE_URL=https://api.anthropic.com/v1/`, `LLM_MODEL=claude-haiku-4-5`.

## Что читать в новой сессии

`AGENTS.md` → `PROJECT_CONTEXT.md` → `DECISIONS.md` (D-10, D-11, D-12) → этот хендовер →
`docs/epics/EPIC-002` и `EPIC-003`.
