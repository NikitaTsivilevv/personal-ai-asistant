# HANDOVER 2026-06-11 - Ночная живая сессия: качество разговора

Четвёртая сессия за день. Живые звонки с Никитой на телефоне (+34653753061). Дошли до
многоходовых разговоров, упёрлись в два бага качества диалога — сессия остановлена,
фиксим в следующей.

## Где остановились

Пайплайн звонка работает целиком: Twilio (теперь **платный аккаунт** — D1 разблокирован) →
Cloudflare quick tunnel → Pipecat → Deepgram → **claude-haiku-4-5 через OpenAI-compat
endpoint Anthropic (D-11)** → Cartesia. 4 живых звонка; бот ведёт многоходовой диалог
(спрашивает доступность, реагирует на ответы). LLM TTFB 0.6–0.7 s (первый ход 2.2 s).

**Два блокирующих бага (фиксить до сценариев D и реальной брони):**

1. **Turn-детекция теряет реплики собеседника.** От disclosure до первого
   зарегистрированного хода юзера ~33 s: речь во время первой фразы бота и короткие
   реплики («si, dime») не триггерят inference (`User stopped speaking (strategy: None)` —
   smart-turn не классифицирует конец реплики). Юзеру приходится повторять 2–3 раза.
   Куда смотреть: конфиг SileroVADAnalyzer + smart-turn в `pipeline.py` (pipecat 1.3,
   `LocalSmartTurnAnalyzerV3`), стратегии стопа `LLMUserAggregator`.
2. **Резидуальная путаница ролей на haiku.** После фикса промпта начало разговора
   корректное («Necesito reservar una cita… ¿Tiene disponibilidad?»), но на этапе данных
   пациента бот снова стал регистратором: «¿A nombre de quién hago la reserva?» — спросил
   собеседника, вместо «a nombre de Nikita» (имя есть в ALLOWED FACTS). Варианты: few-shot
   примеры в промпт; сравнить claude-sonnet-4-6; вернуть gpt-4o-mini (ключ пополнить).

## Что изменилось (НЕ ЗАКОММИЧЕНО — закоммитить в начале следующей сессии)

- `packages/shared/src/assistant_shared/queue.py` — `dequeue_run`/`wait_control` переживают
  `redis.ConnectionError` (warning + 1 s + retry). До этого разрыв TLS Upstash убивал воркер.
- `tests/test_queue_timeouts.py` — +2 теста на ConnectionError.
- `apps/voice-worker/.../call/pipeline.py` — `InboundAudioProbe` между transport.input() и STT:
  логирует число входящих аудио-фреймов и пиковую амплитуду (диагностика «бот не слышит»).
- `apps/voice-worker/.../call/agent.py` — (а) блок `WHO YOU ARE CALLING` с явной ролью
  звонящего (был голый `CALLING: Дента` — haiku представлялся сотрудником Дента);
  (б) high-факты в промпте помечаются `[SENSITIVE: request_approval required before
  disclosure]`, правило 2 требует `request_approval(share_sensitive_data)` до произнесения.
  Это промпт-уровень: значение всё ещё в контексте; структурное удержание значения до
  approval — бэклог (см. risks).
- `tests/test_agent_core.py` — +2 теста (роль, маркировка sensitive).
- `.env` (не в git): `DATABASE_URL` → `postgresql+asyncpg://`; обрезанная последняя строка
  дописана как `STALE_RUN_TIMEOUT_S=300`; LLM переключён на Anthropic (старый OpenAI-конфиг
  в комментарии — у ключа OpenAI `insufficient_quota`); `PUBLIC_WS_URL` → новый туннель.

## Живая БД

Факты засеяны через `/facts`: `nie=Y1715405X` (high, default), `номер машины=7766MFR`
(medium, только insurance), `Имя=Nikita` (понижен high → low, иначе approval на каждое
произнесение имени).

## Валидация

- `uv run pytest -q` — **85 passed** (81 + 4 новых); `uv run ruff check .` — чисто.
- Живые звонки: аудио в обе стороны (зонд: пики 6–9 k), STT/LLM/TTS работают, summary
  доезжает в Telegram. Anthropic OpenAI-compat endpoint проверен с tools.

## Решения

- **D-11** — разговорный LLM = claude-haiku-4-5 через `LLM_BASE_URL=https://api.anthropic.com/v1/`
  (OpenAI-ключ исчерпан; своп D-5 сработал без кода). Пересмотреть после тюнинга качества.

## Открытые вопросы / риски (обновлены)

- Какой минимальный модельный уровень держит роль звонящего (open-questions §Provider).
- Какой конфиг VAD/smart-turn ловит короткие реплики (там же).
- risks.md: +4 строки (turn-детекция, дрейф роли, sensitive-значения в промпте,
  хрупкость стенда — сетевой блип убивает api-процесс и регистрацию quick-туннеля;
  воркер захарднен, api нет).

## Инциденты сессии (для понимания хрупкости стенда)

- Сетевой сбой (DNS) уронил: воркер (Redis ConnectionError — починен в коде), api-процесс
  (getaddrinfo — НЕ починен), регистрацию quick-туннеля (процесс жив, hostname мёртв —
  только перезапуск cloudflared + обновление `PUBLIC_WS_URL` + рестарт воркера).
- Первый ран дня упал на Twilio 400: триал звонил только на верифицированные номера
  (решено апгрейдом Twilio). Тело ошибки Twilio в лог не пишется — стоит добавить.
- cloudflared живёт в `.tools/cloudflared.exe`; лог сессии — `.cloudflared-session.log` (gitignore-кандидат).

## Следующие шаги (= начало следующей сессии)

1. Закоммитить рабочее дерево (ветка + PR: queue resilience, audio probe, prompt fixes).
2. Turn-детекция: разобраться с конфигом smart-turn/VAD, добиться реакции на короткие
   реплики и речь поверх disclosure. Это можно без телефона: юнит/локальные аудио-тесты,
   потом один живой звонок-проверка.
3. Дрейф роли: few-shot в промпт и/или сравнение claude-sonnet-4-6 vs haiku vs gpt-4o-mini
   на одном сценарии. Обновить D-11/цены при смене модели.
4. После фиксов: формальная приёмка Stage 1 (/new → Approve → Reject → пуш итога),
   сценарии EPIC-003 D (doctor approval на nie, insurance deny, restaurant, expiry,
   pause/whisper), затем D1 — реальная бронь (Twilio платный).
5. Бэклог: api-resilience к сетевым сбоям; структурное удержание high-фактов до approval;
   логирование тел ошибок Twilio; named tunnel или VPS вместо quick tunnel.

## Что читать в новой сессии

`AGENTS.md` → `PROJECT_CONTEXT.md` → `DECISIONS.md` (D-10, D-11) → этот хендовер →
`docs/epics/EPIC-002-outbound-calls.md`.
