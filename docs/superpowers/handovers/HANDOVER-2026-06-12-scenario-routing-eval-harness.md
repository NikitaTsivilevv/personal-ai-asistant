# HANDOVER 2026-06-12 — Сценарный роутинг подключён, eval-харнесс построен и проверен вживую

Сессия закрыла пункты (a) и (b) из D-12 одним PR. Вся разработка шла subagent-driven
(implementer + spec-ревью + код-ревью на каждую из 14 задач плана + финальное
интеграционное ревью). Телефона нет — живые шаги по-прежнему отложены.

## Где остановились

`main` содержит PR #1–#10. **PR #10** (https://github.com/NikitaTsivilevv/personal-ai-asistant/pull/10,
+4511/−278): сценарный роутинг живой end-to-end, офлайн eval-харнесс построен и
провалидирован на реальных моделях. 136 тестов, ruff чист. Ветки удалены.

## Что сделано

1. **Сценарий → интейк (D-12 a).** `SCENARIOS` в `assistant_shared.schemas`
   (консистентность с rule-файлами И с enum `Scenario` закрыта тестами);
   `normalize.py` извлекает `scenario` (вне enum → `generic` + warning); карточка
   подтверждения в боте показывает сценарий, кнопка «Сменить сценарий» — выбор из пяти.
   Профили doctor/insurance/restaurant/info_gathering и сценарные факты больше не мертвы.
2. **DI-рефакторинг пайплайна.** Из `run_call_pipeline` извлечён чистый
   `build_call_pipeline` (края/LLM/aggregator-params инжектируются); прод-поведение
   не изменилось (старые тесты — ворота регрессии).
3. **Eval-харнесс (D-12 b), пакет `packages/evals`.** Реальный pipecat-пайплайн с
   текстовыми краями (`AssistantOutputCapture` + инжекция `TranscriptionFrame`-триплетов);
   LLM-симулятор собеседника (персона + обязательные пробы + `[HANGUP]`); approvals по
   скрипту кейса (approve/reject/expire) через настоящий control-list на fakeredis;
   гибридный скоринг — policy (детерминированный, c проверкой утечки sensitive-фактов и
   опц. запретом неожиданных решений), success (judge авторитетен + guards чистого
   завершения и over-claim), role (маркеры + judge), latency (честно подписан «LLM TTFB»),
   cost (по токенам). CLI: `uv run python -m assistant_evals run
   [--scenario X|--case Y] [--runs N] [--max-cost USD]`; JSON-артефакты в `evals-results/`
   (gitignored) с полным транскриптом и event-логом. 6 кейсов × 5 сценариев.
4. **Живой smoke (реальные модели, agent=haiku, judge=sonnet).**
   `doctor/role_drift_probe` — 3/3 по всем осям: оговорка офлайн-A/B из D-11
   (tool-free, single-turn) снята. Полный свип ≈ **$0.05–0.07** (sim+judge) за прогон;
   вся отладка ≈ $0.21. Latency 0.5–1.8 s avg LLM TTFB/ход.
5. **`scripts/eval_role_drift.py` удалён** (поглощён кейсом харнесса).
6. **Доки**: D-13 в `DECISIONS.md`, обновлены `PROJECT_CONTEXT.md`, EPIC-002/003,
   open-questions, risks.

## Главные находки живого прогона (это результаты, не баги харнесса)

- **haiku систематически не вызывает `end_call`/`propose_summary`** — разговор «затухает»
  без чистого завершения. Доминирующий пробел надёжности; теперь измерим.
- **Один случай раскрытия DNI (high) без `request_approval`** — поймала policy-ось.
  Недетерминированно (в другом прогоне того же кейса агент вёл себя верно).
- **Согласие на оплату депозита** в restaurant-кейсе (тоже недетерминированно).
- Прогоны недетерминированы → сигнал только при `--runs 3+`.

## Открытые пункты (зафиксированы в D-13 / risks)

1. **Дизайн кейсов**: `insurance/cancel_denied` и `generic/approval_expiry` ждут, что
   агент *попытается* совершить гейтуемое действие; консервативный вербальный отказ не
   доходит до policy-движка → ложный fail «missing expected decision». Перенастраивать
   только после многопрогонного подтверждения.
2. **Прод-баг, вскрытый ревью**: `tools.py` не передаёт `fact_key` в `ActionRequest` —
   deny-ветка fact-access движка недостижима из воркера.
3. Известный флаки: `tests/test_worker_e2e.py` (order-dependent, таймауты approvals под
   нагрузкой полного прогона; в изоляции проходит). Не связан с этой работой.

## Валидация

`uv run pytest -q` → 136 passed; `uv run ruff check .` → clean; `uv lock --check` → ok.
Живой smoke прогнан трижды (один кейс / role×3 / полный свип с `--max-cost 3.0`).

## Следующие шаги (= начало следующей сессии)

1. **Надёжность стенда (D-12 c)**: супервизия + reconnect для api/bot, план ухода с
   quick-tunnel. №1 блокер реального использования, полностью офлайн.
2. **`end_call`-пропуски haiku**: воспроизвести харнессом (`--runs 5` на
   info_gathering/doctor), попробовать промпт-фикс, измерить до/после. Влияет на D-11.
3. **Обобщение few-shot (D-12 d)** — теперь измеримо тем же способом.
4. **Мелкое**: фикс `fact_key` в `tools.py` (+ кейс на fact-access deny); пересмотр двух
   кейсов с консервативным отказом после многопрогонной статистики.
5. **(нужен телефон)** живая валидация turn-детекции и роли; затем EPIC-003 D,
   EPIC-002 D1, C2/C3.

## Операционные заметки

- Eval: `uv run python -m assistant_evals run --case doctor/role_drift_probe --runs 3`
  (ключ — `LLM_API_KEY`/`LLM_BASE_URL` из `.env`; артефакты в `evals-results/`).
- Стек: `uv run assistant-api` / `assistant-bot` / `assistant-worker`; только ОДИН
  bot-поллер одновременно (Telegram 409).
- Цены моделей для cost-оси — `PRICES_PER_MTOK` в `assistant_evals/llm_client.py`;
  при смене модели дополнить, иначе warning + $0.

## Что читать в новой сессии

`AGENTS.md` → `PROJECT_CONTEXT.md` → `DECISIONS.md` (D-12, **D-13**) → этот хендовер →
`docs/epics/EPIC-002` и `EPIC-003`. Спека/план фичи:
`docs/superpowers/specs/2026-06-12-scenario-routing-eval-harness-design.md`,
`docs/superpowers/plans/2026-06-12-scenario-routing-eval-harness.md`.
