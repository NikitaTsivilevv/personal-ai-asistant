# Техническое задание: личный AI-ассистент для телефонных задач

Версия: 0.1  
Дата: 2026-06-10  
Статус: рабочее ТЗ для MVP

## 1. Цель

Создать личного AI-ассистента, которому можно делегировать бытовые и административные задачи, в первую очередь через телефонные звонки:

- общение со страховой компанией по машине;
- запись к врачу;
- бронь ресторана;
- сбор информации у организаций;
- прием входящих звонков с фильтрацией и кратким summary.

Ассистент должен работать от имени владельца, но не должен притворяться человеком. Безопасная базовая формулировка для звонков: "Soy un asistente de IA llamando en nombre de Nikita" / "I am an AI assistant calling on behalf of Nikita".

## 2. Основные допущения

- Пользователь живет в Испании, поэтому приоритетные языки: испанский, английский, русский.
- Self-hosted LLM/STT/TTS не требуется.
- Предпочтение: собственный backend, собственная логика, собственная база данных, но внешние API для телефонии, распознавания речи, LLM и синтеза речи.
- MVP должен быть дешевым в эксплуатации и может использовать free tiers для dashboard/API/DB/queue.
- Для реальных звонков нужен отдельный долгоживущий voice worker, потому что serverless-функции не являются надежной средой для 15-40 минутных realtime-сессий.

## 3. Объем MVP

### Входит в MVP

- Создание исходящих задач на звонок.
- Live-контроль звонка через dashboard.
- Live transcript.
- Human approvals для чувствительных действий.
- Summary после звонка.
- Хранение задач, звонков, транскриптов, approvals и базовой памяти пользователя.
- Поддержка входящих звонков в ограниченном режиме: screening, summary, transfer to user.
- Подключение календаря и контактов как инструментов ассистента.

### Не входит в MVP

- Полная автономия в юридических, финансовых и медицинских решениях.
- Self-hosted speech/LLM infrastructure.
- Массовые исходящие звонки.
- Продакшен-grade compliance без отдельной юридической проверки.
- Сложная мобильная app-разработка. На MVP достаточно web dashboard и/или Telegram-интерфейса.

## 4. Роли и уровни полномочий

### Пользователь

Создает задачи, задает ограничения, одобряет чувствительные действия, может вмешаться в звонок.

### AI-ассистент

Планирует звонок, ведет разговор, собирает информацию, задает уточняющие вопросы, предлагает действия.

### Policy Engine

Проверяет, можно ли ассистенту сказать или сделать конкретное действие.

### Уровни автономности

| Уровень | Разрешения |
|---|---|
| Level 0 | Только собрать информацию и сделать summary |
| Level 1 | Записать/забронировать в рамках заданных ограничений |
| Level 2 | Менять/отменять что-либо только после approval |
| Level 3 | Финансовые, юридические, медицински чувствительные действия только после ручного подтверждения |

## 5. Пользовательские сценарии

### 5.1 Исходящий звонок: страховая

Пример задания:

> Позвони в страховую по claim X. Узнай статус ремонта машины. Можно назвать номер полиса и DNI. Нельзя соглашаться на платные услуги, закрывать claim или менять условия страховки без моего подтверждения.

Ожидаемый результат:

- ассистент дозвонился;
- представился как AI-ассистент от имени пользователя;
- прошел идентификацию в пределах разрешенных данных;
- собрал статус;
- при необходимости запросил approval;
- сохранил transcript, summary, next steps.

### 5.2 Исходящий звонок: врач

Ассистент должен:

- уточнить доступные слоты;
- выбрать слот по предпочтениям пользователя;
- запросить approval, если требуется раскрыть чувствительные медицинские детали;
- записать в календарь после подтверждения записи.

### 5.3 Исходящий звонок: ресторан

Ассистент может без approval:

- забронировать столик в рамках заданных параметров;
- назвать имя и телефон;
- уточнить условия.

Approval требуется, если:

- нужна предоплата;
- требуется карта;
- условия cancellation/no-show необычные.

### 5.4 Входящий звонок

Ассистент может отвечать на отдельный номер или переадресацию:

- известный номер: применить сценарий;
- неизвестный номер: спросить, кто звонит и по какому вопросу;
- важный звонок: перевести на пользователя;
- спам/робот: завершить;
- после звонка: отправить summary.

Входящие звонки на MVP должны быть консервативными: ассистент не раскрывает личные данные, пока контекст не установлен.

## 6. Целевая архитектура

```text
Web / Telegram / Mobile-lite UI
        |
Backend API
        |
Postgres + Redis/Queue + Object Storage
        |
Agent Orchestrator + Policy Engine
        |
Voice Worker
        |
Telephony Gateway -> STT -> LLM -> TTS -> Phone call
        |
Tools: calendar, contacts, email, docs, browser/API integrations
```

## 7. Компоненты

### 7.1 Frontend / Dashboard

Функции:

- создание задач;
- список задач и статусы;
- live transcript во время звонка;
- кнопки `Approve`, `Reject`, `Take over`, `Hang up`, `Transfer to me`;
- поле для подсказки ассистенту во время разговора;
- просмотр summary, transcript и recording.

Рекомендуемый MVP-хостинг: Vercel Hobby.

### 7.2 Backend API

Возможные технологии:

- FastAPI;
- NestJS;
- Hono/Next.js API routes для легкой части.

Функции:

- auth;
- task management;
- webhook endpoints для телефонии;
- approval API;
- tools API;
- billing/cost tracking;
- audit log.

Легкая часть backend может жить на Vercel. Долгоживущие voice sessions лучше выносить отдельно.

### 7.3 Voice Worker

Отдельный процесс/сервис, который держит realtime-соединения:

```text
Twilio/SIP media stream <-> Voice Worker <-> STT <-> LLM <-> TTS
```

Требования:

- WebSocket/media stream;
- поддержка долгих звонков;
- detection of silence/hold music;
- возможность "усыплять" LLM/TTS во время ожидания;
- reconnect/retry logic;
- live event streaming в dashboard.

Рекомендуемый деплой:

- локально через ngrok/Cloudflare Tunnel для разработки;
- небольшой VPS/Fly.io/Render/Railway/Hetzner для production-like MVP.

### 7.4 Postgres

Рекомендуется как основная БД.

Основные таблицы:

- `tasks`: поручения пользователя;
- `task_runs`: попытки выполнения;
- `calls`: звонки, номера, статусы, длительность, провайдеры;
- `transcript_segments`: транскрипт по сегментам;
- `approvals`: ожидающие и завершенные подтверждения;
- `contacts`: люди и организации;
- `profile_facts`: разрешенные факты о пользователе;
- `documents`: ссылки на документы;
- `audit_log`: важные события и решения.

Для семантической памяти на MVP достаточно `pgvector`.

### 7.5 Redis / Queue

Использование:

- очередь задач;
- временные состояния звонков;
- rate limits;
- pub/sub для live dashboard.

На MVP можно использовать Upstash Redis Free.

### 7.6 Object Storage

Использование:

- аудиозаписи;
- документы;
- вложения;
- экспортированные transcripts.

Варианты:

- Cloudflare R2;
- Supabase Storage;
- S3-compatible storage.

## 8. Рекомендуемый AI/Voice стек

### Базовый MVP-стек

```text
Twilio SIP
Deepgram Flux/Nova
GPT-5.4-mini
Cartesia Sonic
Custom backend + approvals
```

Причины:

- Twilio/SIP проще всего запустить для звонков в Испании.
- Deepgram Flux/Nova хорошо подходит для realtime turn-taking.
- GPT-5.4-mini дает хороший баланс цены, reasoning и tool calling.
- Cartesia Sonic ориентирован на низкую задержку.
- Собственный backend сохраняет контроль над данными, правилами и логикой.

### Альтернативы

| Слой | Основной выбор | Альтернативы |
|---|---|---|
| Telephony | Twilio SIP | Twilio Programmable Voice, Telnyx, Vonage |
| STT | Deepgram Flux/Nova | AssemblyAI Universal Streaming / Universal-3 Pro |
| LLM | GPT-5.4-mini | Claude Haiku, Gemini Flash, GPT-5.4 fallback, Claude Sonnet fallback |
| TTS | Cartesia Sonic | ElevenLabs Flash/Turbo, Deepgram Aura |
| DB | Postgres | Supabase Postgres, Neon Postgres |
| Queue | Redis/Upstash | BullMQ, Celery, Temporal позже |

## 9. Data Flow

### 9.1 Исходящий звонок

```text
1. Пользователь создает задачу.
2. Backend нормализует задачу в structured format.
3. Planner проверяет, хватает ли данных.
4. Если данных не хватает, backend спрашивает пользователя.
5. Voice worker инициирует звонок через telephony provider.
6. STT транскрибирует собеседника.
7. LLM выбирает следующий шаг.
8. Policy Engine проверяет ответ или tool call.
9. TTS озвучивает ответ.
10. Если нужно approval, звонок ставится на паузу или ассистент просит время на подтверждение.
11. После звонка сохраняются transcript, recording, summary, next actions.
```

### 9.2 Входящий звонок

```text
1. Входящий звонок приходит на Twilio/SIP.
2. Telephony provider вызывает webhook backend.
3. Backend определяет caller ID и сценарий.
4. Voice worker принимает звонок или переводит его.
5. Ассистент проводит screening или разговор.
6. При важном звонке ассистент переводит звонок пользователю.
7. После звонка создается summary.
```

## 10. Контроль Диалога

Live dashboard должен показывать:

- текущий статус звонка;
- live transcript;
- текущую цель ассистента;
- последнее решение LLM;
- ожидающие approvals;
- оценку уверенности;
- estimated cost.

Пользователь должен иметь команды:

- `Approve`;
- `Reject`;
- `Take over`;
- `Hang up`;
- `Transfer to me`;
- `Whisper instruction` / подсказка ассистенту;
- `Pause automation`.

## 11. Правила Безопасности

Ассистент должен:

- явно представляться как AI-ассистент;
- не притворяться пользователем-человеком;
- не принимать финансовые, юридические, медицински чувствительные решения без approval;
- не раскрывать лишние персональные данные;
- использовать только данные, разрешенные для конкретной задачи;
- завершать или переводить звонок при неуверенности;
- сохранять audit log важных решений.

Перед production в Испании/ЕС нужна отдельная проверка:

- GDPR;
- правила записи звонков;
- условия telephony provider;
- условия организаций, которым звонит ассистент;
- требования к раскрытию AI/автоматизированного помощника.

## 12. Деплой и Инфраструктура

### Минимальный дешевый MVP

| Компонент | Вариант | Цена |
|---|---|---|
| Frontend | Vercel Hobby | $0 |
| Light backend/API | Vercel Functions | $0 |
| Postgres | Neon Free / Supabase Free | $0 |
| Redis/Queue | Upstash Redis Free | $0 |
| Logs/errors | Vercel logs + Sentry Free | $0 |
| Domain | `*.vercel.app` | $0 |
| Voice worker dev | Local + Cloudflare Tunnel/ngrok | $0 |
| Voice worker production-like | small VPS/Fly/Render/Railway | $5-$10+/month |
| Twilio number | Spain local/national | ~$1-$2/month |

Ориентир без звонков и AI API:

- dev/MVP: $0-$12/month;
- более надежный MVP: $10-$30/month;
- comfortable managed setup: $50-$150/month.

### Почему voice worker не стоит держать только на Vercel Functions

Realtime-звонки требуют:

- долгих соединений;
- WebSocket/media streaming;
- работы дольше обычного HTTP request lifecycle;
- устойчивости при ожидании на линии.

Поэтому Vercel подходит для dashboard/API/webhooks, но voice worker лучше запускать как отдельный долгоживущий процесс.

## 13. Оценка Переменных Расходов

Цены нужно перепроверять перед реализацией. Оценки ниже актуальны по обсуждению на 2026-06-10.

### Телефония Испания

Ориентиры Twilio:

- outbound Spain landline через SIP: ~$0.0138/min;
- outbound Spain mobile from EEA через SIP: ~$0.0348/min;
- inbound: ~$0.0060/min;
- call recording: ~$0.0025/min;
- number: ~$1-$2/month.

### AI pipeline

Ориентир для базового кастомного стека:

```text
Deepgram STT + GPT-5.4-mini + Cartesia/ElevenLabs TTS
```

Примерная AI-себестоимость:

- STT: ~$0.0025-$0.008/min;
- LLM: ~$0.005-$0.03/min при контролируемом контексте;
- TTS: ~$0.01-$0.05/min в зависимости от провайдера и доли речи ассистента.

Итого AI: ~$0.02-$0.08/min.

Итого с телефонией:

- landline: ~$0.04-$0.10/min;
- mobile: ~$0.06-$0.13/min;
- с запасом на retries/hold/tool calls: ~$0.05-$0.15/min.

### Месячные сценарии

При фиксированной инфраструктуре $0-$30/month:

| Использование | Минут/мес | Переменные расходы | Итого |
|---|---:|---:|---:|
| Тестовый режим | 50 | ~$3-$8 | ~$3-$38 |
| Личный MVP | 300 | ~$15-$45 | ~$15-$75 |
| Активное использование | 800 | ~$40-$120 | ~$40-$150 |
| Много звонков | 2000 | ~$100-$300 | ~$100-$330+ |

## 14. Monitoring / Logs / Domain

### Monitoring

Нужен, чтобы понимать:

- упал ли voice worker;
- были ли ошибки STT/LLM/TTS;
- сколько стоит каждый звонок;
- где ассистент завис;
- почему не сработал approval.

MVP:

- Sentry Free для ошибок;
- Vercel logs для frontend/API;
- простая таблица `audit_log` в Postgres;
- healthcheck для voice worker.

### Logs

Нужны разные уровни логов:

- technical logs: ошибки, latency, provider responses;
- audit logs: важные решения ассистента;
- conversation logs: transcript и summary.

### Domain

Кастомный домен необязателен. Для MVP можно использовать `*.vercel.app`.

## 15. Нефункциональные Требования

- Latency: ассистент должен отвечать естественно, без длинных пауз, кроме случаев ожидания approval.
- Reliability: звонок не должен падать из-за перезапуска frontend/API.
- Observability: каждый звонок должен иметь trace: task -> call -> transcript -> approvals -> summary.
- Cost control: система должна показывать estimated cost и отключать лишнюю обработку во время hold music/silence.
- Privacy: данные пользователя должны храниться минимально необходимым образом.
- Recoverability: если звонок оборвался, task_run должен сохранять состояние и результат до обрыва.

## 16. Этапы Реализации

### Этап 1: Control Plane

- Dashboard.
- Auth.
- Postgres schema.
- Создание задач.
- Queue.
- Basic approvals.

### Этап 2: Исходящие Звонки

- Twilio/SIP integration.
- Voice worker.
- STT/LLM/TTS pipeline.
- Live transcript.
- Summary после звонка.

### Этап 3: Human-in-the-loop

- Live approvals.
- Take over / hang up / transfer.
- Policy rules.
- Сценарии для страховой, врача, ресторана.

### Этап 4: Входящие Звонки

- Отдельный номер или переадресация.
- Screening.
- Caller recognition.
- Transfer to user.
- Summary.

### Этап 5: Надежность и Стоимость

- Hold detection.
- Cost dashboard.
- Provider fallback.
- Retry logic.
- Better monitoring.

## 17. Открытые Вопросы

- Какой основной интерфейс выбрать первым: web dashboard, Telegram или оба?
- Какие данные можно хранить в profile_facts: DNI, адрес, номер полиса, дата рождения?
- Нужно ли хранить аудиозаписи или достаточно transcript + summary?
- Какие действия разрешить без approval для каждого сценария?
- Нужна ли интеграция с Google Calendar / Apple Calendar / Outlook?
- Какой номер использовать для входящих: отдельный номер ассистента или переадресация с личного номера?
- Нужно ли требовать AI disclosure на каждом звонке или только в начале разговора?

## 18. Источники для Перепроверки Тарифов

- OpenAI pricing: https://developers.openai.com/api/docs/pricing
- OpenAI Realtime costs: https://developers.openai.com/api/docs/guides/realtime-costs
- OpenAI Voice Agents: https://developers.openai.com/api/docs/guides/voice-agents
- OpenAI Realtime SIP: https://developers.openai.com/api/docs/guides/realtime-sip
- Twilio Voice Spain: https://www.twilio.com/en-us/voice/pricing/es
- Twilio SIP Spain: https://www.twilio.com/en-us/sip-trunking/pricing/es
- Deepgram pricing: https://deepgram.com/pricing
- AssemblyAI pricing: https://www.assemblyai.com/pricing
- ElevenLabs API pricing: https://elevenlabs.io/pricing/api
- Cartesia pricing: https://www.cartesia.ai/pricing/
- Vercel pricing: https://vercel.com/pricing
- Neon pricing: https://neon.com/pricing
- Supabase pricing: https://supabase.com/pricing
- Upstash Redis pricing: https://upstash.com/pricing/redis
- Sentry pricing: https://sentry.io/pricing/

