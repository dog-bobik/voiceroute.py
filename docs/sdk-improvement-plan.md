# План развития voiceroute.py

Дата: 2 ноября 2026. Статус: план реализации, новые API ниже ещё не реализованы.

## Проверенная база

SDK: main, cdeb0b88dff5f107a1ad1a53c80633a66b99af35, версия 0.1.0.dev1.
Платформа: свежий origin/main, 13de59014f91db679eedd898e12cf3fe5441bdf1.
Локальная рабочая копия платформы остаётся на 05cf963; для анализа новых изменений использован git show origin/main без checkout.
OpenAPI платформы содержит 240 операций, capabilities — 83 bot events. Это не процент покрытия SDK: операции имеют разные auth surfaces.
Production deployment не проверялся; checked-in capabilities не доказывают включённость функции в production.

В свежей платформе уже существует отдельный User Gateway с cookie authentication, replay, subscriptions, outbox и feature flags. Встроенный music engine удалён. Bot Gateway сохраняет самостоятельный контракт. Поэтому SDK не должен реализовывать human User Gateway или восстанавливать удалённый встроенный music API.

## Фактическая архитектура SDK и недостатки

- VoiceRouteClient агрегирует 14 resource API; HTTP transport уже поддерживает structured errors, retries, auth strategies, idempotency metadata и ETag.
- Bot владеет client, commands, extensions, dispatcher, Gateway и cache. Создание собственного client внутри Bot затрудняет injection transport и тестирование конфигурации.
- resolve_api_version выбирает режим, но прямо документирован как не меняющий resource routing. Значительная часть ресурсов продолжает ходить по legacy URL.
- MembersAPI.get загружает весь members snapshot и ищет пользователя локально. Сервер уже имеет get/search member endpoints.
- MessagesAPI использует legacy message seq, body и числовой version; v1 UUID messages, rich content и строковые версии требуют отдельного адаптера, а не механической замены URL.
- Gateway startup оставляет compatibility SSE для prefix handlers. Это рабочая совместимость, но увеличивает соединения и усложняет checkpoint/deduplication.
- CommandPipeline уже имеет checks, cooldown, concurrency и middleware; Extension уже поддерживает атомарные load/unload/reload. Их нужно расширять с сохранением существующего API.
- ComponentRouter имеет подписанные custom IDs, но полноценный lifecycle View с timeout, ownership и восстановлением после restart отсутствует.
- VoiceSession и PCM adapter существуют; последние fixes касались disconnected transport. Voice требует runtime capabilities и проверок реального соединения.
- MiniAppsAPI уже содержит bot actions/state: этот домен нельзя планировать с нуля.
- Отдельных resource API uploads, threads, polls, expressions, webhooks, OAuth и durable subscriptions пока нет.
- Generated wire models существуют, но нет versioned snapshots и воспроизводимого operation-to-method coverage manifest.
- CI проверяет Python 3.11–3.13, Ruff/mypy/pytest. Прохождение unit tests не является доказательством live server compatibility.

## Референсы и принятые решения

Используем проверенные механизмы двух библиотек, сохраняя семантику VoiceRoute.

| Референс | Что перенять | Где применять |
| --- | --- | --- |
| aiogram Router | Вложенные routers и композиция handlers | Один dispatcher, независимые пакеты команд |
| aiogram middleware/DI | Request-scoped context и явные зависимости | Prefix, interaction, component и raw events |
| aiogram FSM | Storage protocol, state/data и event isolation | Диалоги, анкеты, onboarding |
| discord.py commands/Cogs | Context, converters, checks и lifecycle extensions | Расширение существующего command engine |
| discord.py app_commands/UI | Typed command tree и View lifecycle | Slash, components, modals |
| discord.py cache/fetch | Явное различие локального get и сетевого fetch | Community/channel/member/message objects |
| discord.py tasks | Lifecycle background loops | Jobs с reconnect, cancellation и teardown |

Источники:

- [aiogram Router](https://docs.aiogram.dev/en/latest/dispatcher/router.html)
- [aiogram dependency injection](https://docs.aiogram.dev/en/latest/dispatcher/dependency_injection.html)
- [aiogram FSM](https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/index.html)
- [discord.py commands](https://discordpy.readthedocs.io/en/stable/ext/commands/api.html)
- [discord.py interactions и UI](https://discordpy.readthedocs.io/en/stable/interactions/api.html)
- [discord.py tasks](https://discordpy.readthedocs.io/en/stable/ext/tasks/index.html)

Не копируем Telegram polling, Discord wire protocol, permission bits или неподдерживаемые VoiceRoute UI-компоненты. Router и Extension используют общий registry, чтобы не создать два конкурирующих pipeline. FSM opt-in, хранилища подключаются extras.

## Целевая структура

```text
voiceroute/
  client.py, bot.py             # совместимые точки входа
  api/                         # typed REST resources
  transport/                   # HTTP, auth, retry, pagination
  gateway/                     # Bot Gateway protocol/session/shards
  events/                      # dispatcher, adapters, checkpoints
  models/generated/            # generated wire DTO
  models/                      # public domain DTO
  commands/                    # prefix/application commands/converters
  routing/                     # Router, filters, context, DI
  ui/                          # View, components, Modal lifecycle
  fsm/                         # Context, storage, isolation
  tasks/                       # supervised background loops
  testing/                     # fake REST/Gateway and fixture factories
  oauth/                       # explicitly separate bearer auth
```

Bound domain helpers могут содержать client reference, но DTO остаются сериализуемыми и пригодными для тестирования без сети. get_* не выполняет I/O; fetch_* и async iterators явно выполняют HTTP. Неизвестные fields/enums сохраняются безопасно. Строковые bigint cursor/version не преобразуются в float/Number; legacy int adapters остаются отдельными.

## Общий Definition of Done

Каждый спринт имеет public API, contract tests точного HTTP/frame payload, runtime integration, пример и документацию. Optional feature проверяется через runtime capabilities. Проверки: Ruff, format, strict mypy src/examples, полный pytest и git diff --check. Новая mutation сохраняет idempotency key при retry и If-Match при необходимости. Auth и секреты не переносятся между origins. Tests на сервере используют изолированную local *_test database. Live tests отмечаются отдельно от mock tests.

Каждый спринт — отдельный законченный срез. Branch только при реализации: feature/... или chore/..., Conventional Commit title без body, merge --no-ff только с разрешением пользователя. Даты и сроки ниже не обещаются: размер уточняется после baseline.

## Последовательность спринтов

### Спринт 1. Контрактная база и coverage

Приоритет и зависимости: P0; зависимостей нет.
Ветка при реализации: `chore/contract-baseline`.

Задачи: Сохранить OpenAPI/AsyncAPI/capabilities/error codes с upstream SHA и SHA256. Классифицировать каждую операцию по botToken/OAuth/human/callback/webhook/public; inherited security учитывать явно. Manifest связывает operation ID с method, DTO, test и статусом full/partial/missing/excluded. Сопоставить 83 события с payload и handlers. CI проверяет drift и воспроизводимость генерации; новые optional endpoints дают отчёт, breaking changes блокируют.

Результат и приёмка: Генерируемая матрица классифицирует 240 операций без фиктивного процента; full требует request/response tests. Новый endpoint и удалённое поле обнаруживаются fixtures.

### Спринт 2. HTTP routing и injectable client

Приоритет и зависимости: P0; 1.
Ветка при реализации: `refactor/client-resource-routing`.

Задачи: Добавить injection client/session в Bot с явным ownership; transport Protocol; pagination helpers, bucket-aware limits и отмену. api_version действительно выбирает resource adapter; fallback только по documented capability, не на любую 403/404. Сохранить текущие constructors.

Результат и приёмка: Тесты legacy/v1/auto, cancellation, foreign-origin redirect, 429 и повтор mutation с тем же ключом. Переданный client не закрывается без ownership.

### Спринт 3. Gateway-first runtime

Приоритет и зависимости: P0; 1–2.
Ветка при реализации: `feature/gateway-command-adapters`.

Задачи: Нормализовать Gateway message/interaction events в существующие Context и pipeline. Убрать обязательный параллельный SSE там, где Gateway payload достаточен. Legacy mode остаётся opt-in/fallback. Resource ordering, bounded queue, handler error policy, cache/checkpoint rollback, invalid Resume reconciliation. Sparse sequence не считать gap по разнице чисел.

Результат и приёмка: Prefix и native command работают при одном Gateway; replay не дублирует reply. Restart/resume, revoked grants, slow handler и неизвестное событие покрыты tests.

### Спринт 4. Domain objects и v1 community resources

Приоритет и зависимости: P0; 2–3.
Ветка при реализации: `feature/v1-community-resources`.

Задачи: Реализовать get/fetch разделение и helpers community/channel/member/role; v1 member lookup/search/iterator вместо full snapshot. Channels/categories CRUD, reorder, clone; role hierarchy, registry, effective permissions, simulate и overrides sync. Registry сохраняет unknown permissions.

Результат и приёмка: Welcome/role bot работает через v1, member lookup делает один точечный запрос, private channel denied; ETag conflict не затирает изменения.

### Спринт 5. Rich messages и uploads

Приоритет и зависимости: P0; 2–4.
Ветка при реализации: `feature/rich-messages-uploads`.

Задачи: UUID message API, embeds, allowed mentions, reply, attachments, pins и versioned edit. File inputs path/bytes/async stream; resumable upload, chunk retry, progress, cancellation, scan result. Лимиты брать из контракта, legacy четыре attachments не выдавать за v1 лимит.

Результат и приёмка: Бот отправляет файл и rich reply, возобновляет upload после сбоя, не буферизует большой файл целиком; scan rejection и retry проверены.

### Спринт 6. Threads, forums и polls

Приоритет и зависимости: P1; 4–5.
Ветка при реализации: `feature/threads-forums-polls`.

Задачи: Thread CRUD/history/membership/archive, forum tags/settings в доступной bot surface. Poll create/vote/results/close; privacy anonymous votes. Cache invalidation по membership loss, thread events и async history iterator.

Результат и приёмка: Support ticket создаёт private thread с вложением; посторонний не получает историю. Poll duplicate delivery не удваивает vote.

### Спринт 7. Router, filters и dependency injection

Приоритет и зависимости: P1; 3–4.
Ветка при реализации: `feature/router-dependency-injection`.

Задачи: Композиционные Router, include_router, фильтры и единый middleware context для всех handlers. Явные root/request-scoped providers; cleanup через async context manager. Extension интегрировать как lifecycle container routers. Сигнатуры проверять при регистрации.

Результат и приёмка: Модуль handlers тестируется без Bot.run; DI resource освобождается при exception/cancel; циклы routers и дубликаты отклоняются.

### Спринт 8. Command ergonomics и hybrid commands

Приоритет и зависимости: P1; 7.
Ветка при реализации: `feature/hybrid-command-framework`.

Задачи: Converters Member/Channel/Role/Enum, choices/defaults, nested groups, help, локальные errors/checks. Единое описание prefix/native handler где типы совместимы; различия acknowledgement остаются явными. Dry-run command sync; удаление чужих remote commands запрещено по умолчанию.

Результат и приёмка: Один compatible handler вызывается prefix и slash; invalid options обнаруживаются до запуска; повтор sync не меняет remote definitions.

### Спринт 9. UI View и modal lifecycle

Приоритет и зависимости: P1; 7–8.
Ветка при реализации: `feature/persistent-views`.

Задачи: View/Button/Select/Modal только из поддержанного server schema. Timeout, disable/stop, ownership check, persistent registration после restart. Подписанные custom IDs с version/key rotation; callback data codecs. Один initial response, defer и followup сохраняют deadline semantics.

Результат и приёмка: Persistent panel переживает restart, чужой пользователь не вызывает действие, repeated callback не выполняет durable action дважды.

### Спринт 10. FSM и диалоговые сценарии

Приоритет и зависимости: P2; 7–9.
Ветка при реализации: `feature/fsm-dialogs`.

Задачи: State/StatesGroup, FSMContext, MemoryStorage/RedisStorage, TTL, clear/update и event isolation. Ключ включает origin/app/community/channel/user по выбранной strategy. Atomic compare/update; state не заменяет durable business transaction.

Результат и приёмка: Onboarding с modal проходит несколько шагов; два concurrent ответа не ломают state; cancel/TTL/storage outage имеют определённое поведение.

### Спринт 11. Оставшиеся bot resources

Приоритет и зависимости: P1; 1,4–6.
Ветка при реализации: `feature/remaining-bot-resources`.

Задачи: v1 AutoMod rules/actions, audit convergence, expressions/stickers, typing/reactions/mentions по bot permissions. Message webhooks с отдельной secret auth, execute/edit/delete и rotation. Не реализовывать human-only mention inbox как bot API.

Результат и приёмка: Manifest закрывает соответствующие операции; webhook secret не попадает в repr/log/exception URL; anonymous/private data redaction проверена.

### Спринт 12. Durable delivery и OAuth/private apps

Приоритет и зависимости: P2; 1–3,11.
Ветка при реализации: `feature/durable-private-delivery`.

Задачи: Subscriptions CRUD/pull/ack, leases, redelivery, signed callback verification raw body, timestamp/replay protection. Разделить ordinary Gateway cursor и durable delivery cursor. OAuth PKCE/refresh через отдельный client/store, private DM с consent/block/delete. Human developer portal оставить отдельным будущим пакетом.

Результат и приёмка: Lease expiry и повтор доставки идемпотентны; signature mismatch отвергнут до dispatch; OAuth credentials никогда не используются BotAuth.

### Спринт 13. Voice и Mini Apps hardening

Приоритет и зависимости: P1; 1–3; можно параллельно после foundation.
Ветка при реализации: `feature/voice-mini-apps-hardening`.

Задачи: Проверить оба серверных voice пути: Gateway grant и bot-token PCM connections. Health/disconnect/drain/cancel, bounded audio queue, join/leave/rejoin, media token refresh и allowed origins. MiniApps state version/actions ack/complete/reject и dedup. Не восстанавливать удалённый server music engine.

Результат и приёмка: Двухсторонний live audio smoke при capability=true; stale voice task не переживает reconnect; capability=false даёт понятный отказ. Mini App action не выполняется повторно.

### Спринт 14. Tasks и testing toolkit

Приоритет и зависимости: P2; 7,12–13.
Ветка при реализации: `feature/tasks-testing-toolkit`.

Задачи: tasks.loop с before/after/error hooks, await ready, cancellation и unload cleanup. FakeGateway/FakeTransport, clock injection, replay fixtures, factories, handler test harness; официальные bot examples support/moderation/persistent panel.

Результат и приёмка: Пример тестируется без сервера и токена; unload оставляет ноль принадлежащих extension tasks; reconnect не создаёт второй loop.

### Спринт 15. Стабилизация и релиз

Приоритет и зависимости: P0 перед стабильной версией; все обязательные предыдущие.
Ветка при реализации: `chore/stabilize-public-api`.

Задачи: Обновить README/API reference/migration guide, py.typed и exports. CI Python matrix, build wheel/sdist, clean-install imports/examples, optional extras отдельно. Benchmark queue/cache/memory; security regression; live conformance pinned server revision. Сначала prerelease, 1.0 только после compatibility window.

Результат и приёмка: Каждый eligible endpoint full либо обоснованное исключение; все supported события проверены; перечень live/skipped tests честный. Версия публикуется только после разрешения.

## Приоритет поставки

Первый релиз-кандидат: спринты 1–5 и 13, чтобы закрыть контрактную надёжность и полезную отправку файлов. Следующий: 6–9 и 11 для framework experience. FSM, OAuth/durable delivery и tasks развиваются после foundation. Спринт 15 завершает каждую release wave частично и всю программу перед 1.0.

Уже работающие Gateway, interactions, cache, extensions и voice не объявляются завершёнными заново: задачи спринтов — конкретные дельты. При изменении upstream сначала обновляется manifest, затем пересматривается зависимый scope.

## Удалённая документация

Устаревшие планы, старые server feature specs и руководства с утверждениями об отсутствующих Gateway/interactions удалены из SDK. Копии сохранены вне checkout в /tmp/voiceroute-docs-backup-7UsQaK. Это временный каталог: для длительного хранения его следует перенести в постоянный архив. Git-tracked файлы также восстанавливаются из HEAD; untracked voice wiring spec сохранён только копией.

Актуальные узкие руководства сохранены как описания существующего API; они не являются доказательством полного v1 покрытия. Полный автоматически проверяемый аудит каждого поля и operation ID — deliverable спринта 1. Production runtime и нагрузочная готовность этим документом не сертифицируются.
