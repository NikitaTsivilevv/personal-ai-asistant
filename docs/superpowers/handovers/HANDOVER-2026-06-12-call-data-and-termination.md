# HANDOVER 2026-06-12 — Первый реальный звонок: разбор, фикс имени брони и гарантия завершения

Сессия началась с разбора первого **реального** исходящего звонка и закончилась
реализацией двух фиксов (D-14) субагентами с пер-задачным spec+quality ревью.
Фикс имени **подтверждён вживую** через eval-харнесс.

## Где остановились

Ветка **`feature/call-data-and-termination`** (не влита, PR ещё не открыт): 12 коммитов
(spec + plan + 10 реализационных). `uv run pytest -q` → **150 passed**, `ruff` чист,
`uv lock --check` ok. `main` по-прежнему PR #1–#10.

## Что разбирали (первый реальный звонок)

Звонок в ресторан Pizza Parking (run `84c4c3c6`, 2026-06-12). **Локального лога нет** —
транскрипт лежит в Neon (`transcript_segments`), достали скриптом через `DATABASE_URL`.
Находки из транскрипта:
- Агент представился и подтвердил бронь **«a nombre de Nikita»** — имя владельца, хотя
  в задаче явно «на имя Victoria». «Victoria» в звонке не прозвучала ни разу.
- Агент сказал полное прощание, но **`end_call` не вызвал** → run завис в `running`,
  ноль tool/policy-событий.
- Плюс: роль-дрифт в конце («que disfruten del cumpleaños» — пожелал ресепшионисту),
  над-обещание («la reserva está confirmada»), STT «Pizza Parking»→«Pisopaylink»,
  транскрипт пишется по одному слову с синтетическим `ts_ms`.

## Корневые причины

- **#1 (имя):** `normalize.py` извлёк «Victoria» в `allowed_facts`, НО воркер трактует
  `allowed_facts` как **whitelist ключей профильных фактов** (`agent.py:allowed_facts`
  фильтрует факты по `key`). «Victoria» не совпала ни с одним профильным ключом
  (`Имя=Nikita`, `nie`, `номер машины`) → молча отброшена. В `ALLOWED FACTS` промпта было
  только `Имя: Nikita`, а few-shot жёстко велел «назови имя из ALLOWED FACTS». Не было
  канала для данных конкретного звонка.
- **#3 (завершение):** правило 6 («call end_call») было мягким, haiku его игнорировал;
  пайплайн финализирует run только при закрытии медиа-потока, а звонок никто не завершал.

## Что сделано (D-14, scope = #1 + #3, выбран пользователем)

1. **`StructuredGoal.call_facts: dict[str,str]`** — канал данных звонка (без миграции, JSON).
   Поток: `normalize.py` (имя третьего лица → call_facts, не allowed_facts) → карточка бота
   → блок `DETAILS FOR THIS CALL` в `build_system_prompt` → переписанный `ROLE_FEWSHOT`
   (имя из DETAILS, иначе из ALLOWED FACTS). Carve-out в правиле 2 (call_facts можно называть
   без approval, в `disclose_fact`-движок НЕ идут). Strip переводов строк (анти-инъекция).
2. **Завершение:** правило 6 → «you MUST call end_call»; `TERMINATION_WRAPUP`; настройки
   `max_call_duration_s=360`/`max_call_turns=16`; чистый **`TerminationGuard`**
   (`call/termination.py`, юнит-тесты) + watchdog по длительности и счётчик ходов
   (по `UserStoppedSpeakingFrame`) в `run_call_pipeline`; единоразовый `try_fire()`.
   Eval-харнесс не задет (`on_callee_turn=None` по умолчанию).
3. **Eval:** кейс `restaurant/booking_third_party` (имя брони Victoria ≠ профильное Nikita);
   флаг `require_end_call` на `EvalCase` + проверка в `score_success`.

## Живая валидация (ключи из `.env`)

- **`restaurant/booking_third_party` ×3:** агент говорит **«a nombre de Victoria»**, не Nikita;
  policy/role/success — PASS (после правки `expected_end_outcome: achieved`; role 1/3 упал из-за
  #2 — агент спросил у ресепшиониста «¿cuántas personas?», вне scope). **Главный баг закрыт.**
- **`end_call` `--runs 5`:** info_gathering 2/5, doctor/booking_basic 3/5, doctor/role_drift_probe 5/5.
  Промпт-nudge помог, но **добровольный `end_call` у haiku ненадёжен**. Прод-завершение
  гарантирует backstop (его харнесс НЕ воспроизводит → на флагманском кейсе `require_end_call`
  намеренно НЕ ставим, иначе флаки не из-за прод-бага).
- Стоимость всех прогонов sim+judge ≈ $0.13.

## Решения

- **D-14** добавлено в `DECISIONS.md` (call_facts + termination backstop, с живыми находками).

## Обновлённые доки

`DECISIONS.md` (D-14), `PROJECT_CONTEXT.md`, `EPIC-002`, `docs/product/risks.md`
(имя брони, end_call+backstop, роль-дрифт data-stage, over-claim, STT, гранулярность транскрипта),
`docs/product/open-questions.md` (end_call частично закрыт, транскрипт/STT). Спека и план:
`docs/superpowers/specs/2026-06-12-call-data-and-termination-design.md`,
`docs/superpowers/plans/2026-06-12-call-data-and-termination.md`.

## Открытые вопросы / риски

- Добровольный `end_call` у haiku низкий — менять ли модельный пол (D-11) или backstop достаточно?
- Роль-дрифт на стадии данных (#2): few-shot покрывает имена, не прочие недостающие данные.
- Над-обещание результата (#4); STT-мисхиры; пословный транскрипт с синтетическим `ts_ms`.
- Стоящий `fact_key` в `tools.py`; два кейса с консервативным отказом (D-13).
- Реальная причина зависшего `running` в тестовом звонке — вероятно остановка воркера
  (D-12 c супервизия), не только отсутствие `end_call`.

## Следующие шаги

1. Открыть/влить PR ветки `feature/call-data-and-termination`.
2. Супервизия api/bot (D-12 c); уход с quick-tunnel.
3. Обобщить few-shot на «недостающие данные» (#2); решить по модельному полу (D-11).
4. Полировка из реального звонка: анти-over-claim в промпте, агрегация транскрипта,
   keyterm-хинты Deepgram; `fact_key`; два eval-кейса.
5. (нужен телефон) перезвонить в Pizza Parking и подтвердить фиксы вживую; затем
   EPIC-003 D, EPIC-002 D1, C2/C3.

## Что читать в новой сессии

`AGENTS.md` → `PROJECT_CONTEXT.md` → `DECISIONS.md` (D-13, **D-14**) → этот хендовер →
`docs/epics/EPIC-002` / `EPIC-003`. Спека/план D-14 — ссылки выше.
