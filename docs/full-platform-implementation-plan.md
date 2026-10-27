# Полный план реализации `voiceroute.py`

## 1. Назначение документа

Этот документ задаёт последовательность превращения `voiceroute.py` в полноценную
асинхронную Python-библиотеку для всей Bot Platform
[VoiceRoute](https://voiceroute.cc): от низкоуровневых REST/Gateway контрактов до
эргономичного фреймворка уровня `discord.py` и `aiogram`.

План составлен по состоянию:

- VoiceRoute Bot Platform v1: `origin/main` на коммите `a8ef852`;
- Python SDK: `main` на коммите `2608dfb`;
- опубликованный контракт VoiceRoute: 213 REST operations и 76 domain events;
- maturity серверной платформы: `experimental`, stages `A/B/C/D/E`;
- legacy REST/SSE остаются включёнными, дата sunset отсутствует;
- `voiceTransport`, `privateMedia` и production sandbox могут быть выключены runtime
  capabilities конкретного deployment.

Документ является master roadmap. Старые `docs/roadmap.md` и `docs/api-coverage.md`
должны быть постепенно заменены ссылками на этот план и автоматически генерируемую
матрицу покрытия.

## 2. Главная цель

Разработчик Python-бота должен иметь возможность:

- установить пакет и запустить полезного бота с минимальным boilerplate;
- использовать Gateway, intents, resume, sharding и state cache без ручной реализации;
- работать со всеми bot-compatible REST resources VoiceRoute;
- создавать slash, user и message commands;
- отвечать на interactions, autocomplete, buttons, selects и modals;
- отправлять rich messages, files, replies, polls и webhooks;
- управлять communities, channels, categories, roles, members и permissions;
- использовать threads, private threads, expressions и AutoMod;
- получать все 76 событий через типизированный dispatcher;
- выбирать Gateway, durable pull или подписанные HTTPS callbacks;
- использовать OAuth/user installations/application DM там, где это разрешено;
- подключать voice только при фактическом `voiceTransport=true`;
- сохранять совместимость существующих legacy-ботов;
- тестировать код без живого сервера через официальный conformance набор.

## 3. Критерий полного покрытия

Нельзя считать библиотеку полностью покрывающей VoiceRoute только потому, что для каждого
URL существует метод. Полное покрытие домена означает одновременно:

1. Все применимые operation IDs OpenAPI представлены публичным Python API.
2. Request и response имеют типизированные модели.
3. String cursor/sequence/version никогда не преобразуются в `int`.
4. Structured errors преобразуются в устойчивую иерархию исключений.
5. Mutation поддерживает idempotency и optimistic concurrency, если это требует сервер.
6. Rate-limit headers учитываются транспортом.
7. Capability проверяется до использования optional feature.
8. Есть contract tests по официальным fixtures или точному HTTP payload.
9. Есть хотя бы один пользовательский пример либо раздел документации.
10. Высокоуровневый `Bot` интегрирует realtime-события домена.
11. Legacy и v1 поведение либо эквивалентны, либо различие явно задокументировано.
12. Неизвестные optional fields и enum values не ломают клиент.

## 4. Границы продукта

### 4.1. Что покрывает основной пакет

- Bot token REST и Gateway.
- Application interactions и callback tokens.
- Durable subscriptions и signed event delivery helpers.
- OAuth bearer/client-credentials ресурсы.
- User installation и private application APIs при наличии OAuth consent.
- Voice state и media adapter при runtime capability.
- Legacy REST/SSE для совместимости и legacy-only операций.
- Общие модели OpenAPI/AsyncAPI и conformance fixtures.

### 4.2. Что выделяется в отдельный namespace

Human-session endpoints кабинета разработчика не должны случайно использоваться обычным
ботом. Для них создаётся отдельный namespace `voiceroute.developer` и отдельный
`DeveloperClient` с явно переданным human-session transport. Bot token туда не
подставляется автоматически.

К ним относятся:

- создание и изменение Applications;
- developer team и invitations;
- bot/client credential rotation;
- application metadata/branding;
- Gateway intent settings и diagnostics;
- sandbox runs;
- service incident/operator-only функции, если они вообще становятся публичными.

### 4.3. Что не имитируется библиотекой

- Пароль, MFA и cookie не запрашиваются через `VoiceRouteClient`.
- Библиотека не обходит privileged intent review.
- Она не объявляет voice доступным при `voiceTransport=false`.
- Она не подменяет server permissions локальными checks.
- Она не считает наличие маршрута доказательством production availability.
- Она не превращает пользовательские/private endpoints в bot endpoints.

## 5. Архитектура целевого пакета

```text
voiceroute/
├── client.py                 # основной Bot client
├── bot.py                    # high-level runtime
├── config.py
├── errors.py
├── transport/
│   ├── http.py               # legacy + v1 HTTP
│   ├── auth.py               # Bot/OAuth/callback/webhook auth strategies
│   ├── idempotency.py
│   ├── rate_limit.py
│   ├── pagination.py
│   └── retry.py
├── gateway/
│   ├── client.py
│   ├── intents.py
│   ├── presence.py
│   ├── sharding.py
│   ├── store.py
│   └── voice.py
├── events/
│   ├── dispatcher.py
│   ├── generated.py
│   ├── delivery.py
│   └── legacy.py
├── api/
│   ├── platform.py
│   ├── applications.py
│   ├── commands.py
│   ├── interactions.py
│   ├── messages.py
│   ├── uploads.py
│   ├── polls.py
│   ├── communities.py
│   ├── members.py
│   ├── roles.py
│   ├── channels.py
│   ├── categories.py
│   ├── permissions.py
│   ├── threads.py
│   ├── expressions.py
│   ├── automod.py
│   ├── webhooks.py
│   ├── subscriptions.py
│   ├── oauth.py
│   ├── private.py
│   ├── voice.py
│   └── legacy_*.py
├── models/
│   ├── generated/            # generated wire DTO
│   ├── domain/               # ergonomic public models
│   └── compatibility/        # legacy adapters
├── commands/
├── components/
├── state.py
├── oauth/
├── webhooks/
├── voice/
├── developer/
├── testing/
└── ext/
```

Wire DTO и высокоуровневые domain models разделяются. Генератор может обновить wire DTO
по OpenAPI/AsyncAPI, но не должен перезаписывать вручную спроектированный публичный API.

## 6. Уже реализованная база

Перед началом новых доменов необходимо сохранить существующую функциональность:

- async HTTP transport, auth, retries и rate limiter;
- legacy communities/channels/messages/content APIs;
- legacy members, permissions, roles, moderation, AutoMod и audit;
- legacy SSE и cursor stores;
- prefix command framework;
- application command и interaction foundation;
- extensions, middleware, checks, cooldowns, concurrency limits;
- supervised bot lifecycle;
- Bot Platform v1 capability discovery;
- current application и Gateway discovery;
- WebSocket Identify/Resume/heartbeat/reconnect;
- intents, privileged intent validation, sharding и presence;
- member chunk request и Gateway subscription control frames;
- unified event dispatcher, waiters и deduplication;
- generated event payload foundation;
- Gateway-aware state cache и reconciliation;
- `legacy`, `v1`, `auto` compatibility policy;
- Gateway runtime examples.

Каждый следующий этап обязан прогонять старые contract/unit/example tests.

## 7. Git-процесс реализации

Каждый этап выполняется отдельно:

1. Создать ветку допустимого вида `feature/...`, `refactor/...`, `test/...` или `docs/...`.
2. Не использовать префикс `codex/`.
3. Разделить commits по логическим изменениям: models/transport, public API, runtime,
   tests, docs.
4. Использовать английские Conventional Commit titles без body.
5. Выполнить Ruff, format check, strict mypy и полный pytest.
6. Проверить `git diff --check` и отсутствие секретов.
7. Merge в `main` только через `git merge --no-ff`.
8. Не удалять feature branch до подтверждённого push.
9. После push проверить `origin/main...main == 0 0`.

Рекомендуемый размер одной ветки: один законченный вертикальный срез, который можно
объяснить пользователю и протестировать независимо.

---

# Последовательность реализации

## Этап 0. Контрактная фиксация и автоматическая матрица покрытия

**Ветка:** `chore/platform-contract-baseline`

### Задачи

- Сохранить поддерживаемый snapshot `openapi.json`, `asyncapi.json`,
  `capabilities.json`, `error-codes.json` и conformance fixtures.
- Записывать upstream commit/hash спецификаций.
- Создать генератор `scripts/check_api_coverage.py`.
- Сопоставить каждый operation ID с Python method либо явным исключением.
- Сопоставить все 76 events с typed payload и handler name.
- Разделить операции по auth surface: Bot, OAuth, human session, callback capability,
  webhook secret и public discovery.
- Создать `docs/generated/api-coverage.md` и JSON-версию для CI.
- Падать в CI при исчезновении operation ID, несовместимой schema или новом непокрытом
  обязательном событии.
- Не падать на новом optional operation, но отмечать его как `unimplemented`.

### Пользовательский результат

Пользователь видит честное, воспроизводимое покрытие, а не приблизительную таблицу.

### Критерий завершения

- Все 213 текущих REST operations классифицированы.
- Все 76 events классифицированы.
- Для каждого исключённого endpoint указана причина.
- CI обнаруживает drift спецификации.

## Этап 1. Завершение v1 HTTP transport — выполнено

**Ветка:** `feature/v1-http-transport`

**Статус:** ✅ Выполнено 26 октября 2026 года.

Реализация: `transport/http.py`, `transport/auth.py`, `errors.py` и contract tests.

### Задачи

- Поддержать `X-VoiceRoute-API-Version` и `X-Request-ID`.
- Реализовать structured error envelope.
- Сохранить неизвестный error code и `details`.
- Добавить `fieldErrors`.
- Ввести исключения `AuthenticationRequired`, `BotAuthenticationRequired`,
  `MissingPermission`, `VersionConflict`, `IdempotencyConflict`, `PayloadTooLarge`,
  `RequestCapacity`, `FeatureUnavailable`.
- Считать `retryable`, `Retry-After` и `details.retryAfterMs`.
- Реализовать автоматический UUID `Idempotency-Key` только для явно безопасных helper
  methods.
- Один logical retry обязан использовать тот же key и то же тело.
- Добавить `If-Match`/ETag helpers.
- Добавить response size limit, concurrency limit и cancellation.
- Запретить redirects для credentialed requests.
- Не отправлять Authorization на другой origin.
- Реализовать auth strategies для Bot, OAuth Bearer, Basic token exchange, callback token,
  webhook secret и MiniApp credential в будущем.
- Сохранить legacy error parser.

### Пользовательский результат

Ошибки становятся машинно различимыми, безопасные mutation можно повторять после сетевой
неопределённости, а version conflicts не перезаписывают чужие изменения.

### Тесты

- Все error fixtures.
- Retry с одинаковым idempotency key.
- Reuse key с другим body.
- 429/503/capacity.
- Cross-origin redirect.
- Unknown code/details.
- Legacy envelope regression.

## Этап 2. Генерация wire models и стабильные domain models — выполнено

**Ветка:** `feature/generated-models`

**Статус:** ✅ Выполнено 26 октября 2026 года.

Реализация: воспроизводимый `scripts/generate_wire_models.py`, внутренний пакет
`models/generated`, forward-compatible primitives в `models/wire.py` и unit tests.

### Задачи

- Генерировать internal dataclasses/TypedDict/enums из OpenAPI и AsyncAPI.
- Все ID, cursor, sequence и version хранить строками.
- Unknown enum value сохранять через tolerant wrapper, не выбрасывать `ValueError`.
- Различать omitted, explicit `null` и default.
- Реализовать forward-compatible additional properties.
- Создать domain model adapters.
- Добавить `to_dict()` только там, где объект является request body.
- Не генерировать бизнес-методы в model classes.
- Зафиксировать naming policy `camelCase -> snake_case`.
- Сделать generated files reproducible и проверять clean diff в CI.

### Пользовательский результат

IDE показывает точные типы, а новый optional field сервера не ломает работающего бота.

### Критерий завершения

- Event fixtures парсятся полностью.
- Protocol fixtures парсятся полностью.
- Повторная генерация не меняет repository diff.
- Public models не зависят от порядка properties в OpenAPI.

## Этап 3. Доведение Gateway до production-ready runtime — выполнено

**Ветка:** `feature/gateway-runtime`

**Статус:** ✅ Выполнено 26 октября 2026 года.

Реализация: bounded dispatch queue с отдельным control-frame path, heartbeat ACK watchdog,
jittered reconnect, session-start guard, close-code policy, graceful drain, metrics,
checkpoint leases, process-local/Redis/PostgreSQL backends и coordinated sharding.

### Уже имеется

Identify, Resume, heartbeat, reconnect, intents, presence, checkpoints, shard primitives,
member chunks и subscription update.

### Дополнить

- Полная обработка close codes и server reconnect.
- Jittered exponential backoff.
- Identify concurrency и session start limits.
- Контроль отсутствующего heartbeat ACK.
- Bounded dispatch queue и backpressure.
- Отдельный fast path control frames, не заблокированный долгим handler.
- Session invalidation callbacks.
- Graceful drain при shutdown.
- ShardManager с последовательным Identify.
- Межпроцессный checkpoint ownership contract.
- Redis/PostgreSQL checkpoint adapter.
- Metrics hooks без токена/session ID.
- Fallback reconciliation при невозможном Resume.
- Опциональная проверка capabilities refresh после close 4014/4015.

### Пользовательский результат

Бот переживает сетевые разрывы, рестарт процесса и rolling deploy без ручной работы с
WebSocket.

## Этап 4. Полный каталог событий и high-level handlers — выполнено

**Ветка:** `feature/event-catalog`

**Статус:** ✅ Выполнено 27 октября 2026 года.

Реализация: каталог всех 76 событий, forward-compatible raw envelope, ergonomic handler
aliases, `@bot.listen()`, `wait_for()`, bounded concurrency и causal ordering по resource key.

### Задачи

- Типизировать все 76 events.
- Сгенерировать `on_<event_name>` aliases.
- Сохранить raw event для неизвестных будущих событий.
- Разделить control frames и domain events.
- Добавить decorators `@bot.event`, `@bot.listen()` и `wait_for()` для v1.
- Определить до/после cache snapshots для update/delete событий.
- Гарантировать commit cursor только после успешной обработки.
- Не продвигать cursor после необработанной ошибки.
- Определить error isolation policy для нескольких listeners.
- Добавить configurable event concurrency по resource key.
- Сохранить причинный порядок внутри resource, не обещать глобальный порядок.

### Группы событий

- application/installations;
- communities/channels/categories/roles;
- members/presence/chunks;
- messages/pins/reactions/typing;
- interactions;
- threads/thread members;
- bans/timeouts/AutoMod/audit;
- webhooks;
- expressions;
- polls;
- voice/stage/soundboard;
- direct messages/private installations/privacy;
- attachment scan.

### Пользовательский результат

Работают привычные handlers `on_member_join`, `on_message`, `on_reaction_add`,
`on_thread_create`, `on_automod_action` и остальные события.

## Этап 5. State cache 2.0 и converters — выполнено

**Ветка:** `feature/domain-cache`

**Статус:** ✅ Выполнено 27 октября 2026 года.

Реализация: typed cached entities, partial/redacted snapshots, отдельные domain policies,
bounded LRU, opt-in message cache, rollback, REST reconciliation и explicit converters.

### Задачи

- Заменить generic `CachedEntity` на typed cached domain entities поверх wire snapshots.
- Поддержать partial/redacted state.
- Кэшировать categories, polls, expressions, bans, voice states и installations по
  отдельной policy.
- Добавить bounded LRU и per-domain limits.
- Добавить message cache opt-in.
- Rollback cache при handler failure.
- Reconciliation по v1 REST с fallback на legacy только в auto mode.
- Converters: member, user, role, channel, message, thread, expression, command target.
- Lazy fetch для cache miss.
- Запрет implicit network I/O в простых properties.
- Документировать consistency model.

### Пользовательский результат

Handlers получают богатые объекты вместо словарей, но память и сетевые запросы остаются
предсказуемыми.

## Этап 6. Current application, capabilities и service status — выполнено

**Ветка:** `feature/platform-bootstrap`

**Статус:** ✅ Выполнено 27 октября 2026 года.

Реализация: полностью типизированные capability sections, status/incidents, runtime
OpenAPI/AsyncAPI, TTL cache, explicit refresh, feature guards и safe startup diagnostics.

### Операции

- `getCapabilities`;
- `getPlatformServiceStatus`;
- `getOpenApi`;
- `getAsyncApi`;
- `getGateway`;
- `getCurrentBotApplication`.

### Задачи

- Типизировать все capability sections.
- TTL cache и explicit refresh.
- `client.require_feature()`.
- Service degradation helpers.
- Application identity, requested/approved intents.
- Safe diagnostics для startup log без токена.
- Не использовать bundled capabilities вместо runtime response.

### Пользовательский результат

Бот заранее объясняет, почему функция недоступна, вместо случайного 404/403.

## Этап 7. Application commands v1 — выполнено

**Ветка:** `feature/v1-application-commands`

**Статус:** ✅ Выполнено 27 октября 2026 года.

Реализация: global/community CRUD и atomic sync, discovery, dry diff, command
permissions, ETag/idempotency, три command type, contexts и полный option tree.

### Операции

- global command list/create/get/update/delete/sync;
- community command list/create/get/update/delete/sync;
- channel/community discovery;
- command permissions get/replace/list.

### Задачи

- Поддержать `CHAT_INPUT`, `USER`, `MESSAGE`.
- Вложенные subcommands/groups.
- Все option types, choices, min/max, autocomplete.
- Contexts `COMMUNITY`, `BOT_DM`, `PRIVATE_CHANNEL`.
- Global/community scope decorators.
- Atomic sync с сохранением server IDs.
- Dry diff перед sync.
- ETag/idempotency.
- Default member permissions.
- Role/member/channel command rules.
- Поведение unknown command type/options.

### Пользовательский результат

Разработчик объявляет команды Python-декораторами и одной операцией синхронизирует их с
VoiceRoute.

## Этап 8. Interactions, autocomplete, components и modals — выполнено

**Ветка:** `feature/rich-interactions`

**Статус:** ✅ Выполнено 27 октября 2026 года.

Реализация: v1 interaction payloads, initial/deferred callbacks, autocomplete, follow-ups,
edit/delete original, components, modals, private operations и signed persistent routing.

### Операции

- invoke/get interaction;
- component interaction;
- modal submission;
- initial callback;
- follow-up create/get/edit/delete;
- private interaction equivalents.

### Задачи

- Deadline 3 секунды.
- `defer()`, `send_message()`, `edit_original()`, `delete_original()`.
- Ephemeral-by-default для private contexts.
- Follow-ups и token TTL.
- Autocomplete result API.
- Buttons, string/user/role/channel selects.
- Modals и typed fields.
- Update/deferred update response.
- Interaction token не хранить в cursor stores/logs.
- Context-aware resolved targets.
- Persistent component routing после рестарта.
- `custom_id` signing/size policy.

### Пользовательский результат

Можно создавать интерактивные интерфейсы с кнопками, меню, autocomplete и формами без
ручной работы с callback URLs.

## Этап 9. Permission registry и simulation

**Ветка:** `feature/v1-permissions`

### Операции

- permission registry;
- effective member permissions;
- permission simulation;
- channel/category overrides;
- override sync.

### Задачи

- Загружать registry с сервера, не фиксировать навечно enum.
- Ergonomic known Permission constants плюс unknown values.
- `Permissions` как immutable set.
- `has()`, `require()`, `missing()`.
- Effective permissions для member/channel.
- Simulation request builder без mutation.
- Typed override targets.
- Category inheritance и channel sync state.
- High-level command checks использовать server-compatible semantics.

### Пользовательский результат

Бот может безопасно показывать preview изменения прав и проверять фактический доступ.

## Этап 10. Members и member lifecycle

**Ветка:** `feature/v1-members`

### Операции

- list/get/search members;
- update member;
- add/remove role;
- effective permissions;
- Gateway member chunks.

### Задачи

- Opaque query-bound cursor pagination.
- Literal search semantics.
- Member vs User.
- Nickname, pending, timeout и version fields.
- `fetch_member`, `search_members`, async iterator.
- `request_members` aggregate helper по chunks/nonce.
- `on_member_join/update/remove`.
- Privileged `members` intent handling.
- Current visibility and permission recheck.

### Пользовательский результат

Полноценные welcome/moderation/role automation боты без polling.

## Этап 11. Roles v1

**Ветка:** `feature/v1-roles`

### Операции

- list/create/get/update/delete;
- reorder;
- member role add/remove.

### Задачи

- Versioned Role model.
- Decorations: color/icon/unicode emoji, если advertised schema поддерживает.
- Managed/builtin role restrictions.
- Hierarchy validation как UX hint, но server остаётся authority.
- Atomic order replacement.
- Legacy bulk assignment adapter.
- Role events и cache integration.

### Пользовательский результат

Бот управляет полной иерархией ролей и визуальными атрибутами.

## Этап 12. Channels и categories v1

**Ветка:** `feature/v1-channel-management`

### Операции

- channel list/create/get/update/delete/order/clone;
- category list/create/get/update/delete/order;
- category/channel permission endpoints и sync.

### Задачи

- Полные channel kinds/presentation.
- Typed create/update builders.
- Category placement и order.
- Forum/channel settings.
- Clone options.
- Versions/ETag/idempotency.
- Delete side effects и cache invalidation.
- Events order/update/delete.

### Пользовательский результат

Можно программно строить структуру сообщества, клонировать шаблоны и синхронизировать
права.

## Этап 13. UUID messages и rich content

**Ветка:** `feature/v1-messages`

### Операции

- channel/thread message list/create/get/update/delete;
- atomic bulk delete;
- interaction/webhook message variants.

### Задачи

- UUID message ID как primary v1 identity.
- Сохранить legacy `seq` отдельно.
- Cursor list.
- Version/If-Match.
- Reply references и immutable reply snapshot.
- Allowed mentions с безопасным default no-ping.
- Embeds, rich blocks и application attribution.
- Components attachment.
- Flags и ephemeral constraints.
- Atomic bulk moderation с reason.
- Message builder и fluent API.
- Redacted message content без privileged intent.
- Точное различие deleted/tombstone/not visible.

### Пользовательский результат

Бот отправляет современные rich messages, отвечает на сообщения по UUID и безопасно
редактирует их без race conditions.

## Этап 14. Resumable uploads, files и protected images

**Ветка:** `feature/files-and-uploads`

### Операции

- upload create/get/cancel;
- upload part;
- complete;
- file metadata/content;
- protected image retrieval.

### Задачи

- Async streaming без загрузки файла целиком в память.
- 1 MiB parts и parallel part policy.
- Whole/part SHA-256.
- Resume после разрыва.
- AbortSignal/cancellation.
- Progress callback.
- AV states pending/ready/rejected.
- Attachment ownership и context binding.
- Range download.
- Filename/MIME/spoiler.
- Temp file cleanup.
- Application storage quota.
- Защита токенов/URL в логах.

### Пользовательский результат

Можно надёжно отправлять вложения и продолжать большую загрузку после сетевого сбоя.

## Этап 15. Reactions, typing и mentions

**Ветка:** `feature/message-signals`

### Операции

- clear message reactions;
- start/list typing;
- own mentions list/ack;
- reaction events.

### Задачи

- Reaction model: unicode/custom expression.
- Add/remove остаются совместимыми с legacy, пока v1 operation отсутствует.
- Clear all/emoji с permission check.
- Typing context manager с bounded refresh.
- Mentions cursor и exact deep links.
- Explicit notification policy.
- ACK idempotency.
- No-ping default в message builder.

### Пользовательский результат

Бот корректно показывает typing, управляет реакциями и обрабатывает входящие упоминания.

## Этап 16. Polls

**Ветка:** `feature/polls`

### Операции

- create/get/close poll;
- set/remove own ballot;
- list voters.

### Задачи

- Single/multiple choice.
- Anonymous mode.
- Expiry и manual close.
- Immutable result snapshots.
- Permission-sensitive voter listing.
- Poll events и cache.
- Fluent PollBuilder.

### Пользовательский результат

Боты создают нативные опросы и реагируют на голоса без парсинга сообщений.

## Этап 17. Threads, forums и private membership

**Ветка:** `feature/v1-threads`

### Операции

- list/create/get/update/delete threads;
- current membership get/join/leave;
- members list/add/remove;
- thread UUID messages и bulk delete.

### Задачи

- Public/private thread model.
- Archived/locked/invitable state.
- Forum tags/guidelines settings, включая legacy adapter при необходимости.
- Membership visibility.
- Thread history async iterator.
- Attachments/rich/components в thread messages.
- Thread events и member events.
- Current ACL при replay.

### Пользовательский результат

Можно создавать support/forum/workflow-ботов с приватными ветками и управляемым членством.

## Этап 18. Expressions: emoji и stickers

**Ветка:** `feature/expressions`

### Операции

- emoji list/create/get/update/delete;
- sticker list/create/get/update/delete.

### Задачи

- Раздельные Emoji/Sticker models.
- Upload/scan workflow.
- Availability и role restrictions.
- Versions/idempotency.
- Animated/static metadata.
- Expression references в message builder и reactions.
- Events/cache.
- Legacy expression adapter.

### Пользовательский результат

Боты создают и используют нативные emoji/stickers с безопасной загрузкой файлов.

## Этап 19. Moderation v1 и audit convergence

**Ветка:** `feature/v1-moderation`

### Задачи

- Сохранить legacy kick/ban/unban/timeout API до появления v1 equivalents.
- Привязать операции к Gateway BAN/TIMEOUT events.
- Typed reason и audit correlation.
- Member hierarchy/preflight hints.
- Audit cursor, actors/actions filters.
- New audit action types: polls, threads, expressions, voice policy, AutoMod rules.
- Consistent moderation checks и errors.
- Reason propagation в bulk message delete.

### Пользовательский результат

Модерационный бот видит действия realtime, связывает их с audit log и использует единые
модели старого и нового API.

## Этап 20. AutoMod rules

**Ветка:** `feature/automod-rules`

### Операции

- actions list;
- rules list/create/get/update/delete;
- channel alerts.

### Задачи

- Rule trigger types: keywords, presets, RE2, mentions, domains.
- Actions: block, alert, timeout.
- Exempt roles/channels/users по schema.
- Version/idempotency.
- Rule validation и regex safety feedback.
- Metadata-only action log.
- Live alert events.
- Legacy aggregate config adapter без ложной эквивалентности.

### Пользовательский результат

Бот управляет отдельными AutoMod rules и получает информацию о срабатываниях.

## Этап 21. Message webhooks

**Ветка:** `feature/message-webhooks`

### Операции

- webhook CRUD/rotate;
- execute webhook;
- webhook message get/edit/delete.

### Задачи

- Secret показывается один раз и не попадает в repr/log.
- Separate `WebhookClient` без Bot Authorization.
- Username/avatar policy.
- Rich messages/files/components.
- Parent channel/thread target.
- Wait/result behavior, если доступно schema.
- Rotation и old-secret invalidation.
- Attribution model.
- SSRF-safe avatar/image use.
- Events/cache/audit.

### Пользовательский результат

Можно строить входящие интеграции, которые публикуют rich content от отдельной webhook
identity.

## Этап 22. Durable event delivery и signatures

**Ветка:** `feature/durable-delivery`

### Операции

- delivery status;
- verification keys;
- subscription CRUD;
- pull;
- delivery list/get/ack/replay;
- signing key rotation.

### Задачи

- Models transport/mode/filter.
- Pull async iterator.
- Explicit ACK после commit пользователя.
- Lease/fencing semantics.
- Dead-letter inspection и manual replay.
- Ed25519 exact-byte verification helper.
- Timestamp/replay window.
- Constant-time validation where applicable.
- ASGI adapter для FastAPI/Starlette без обязательной framework dependency.
- WSGI/basic helper отдельно, если оправдано.
- Subscription delivery cursor не смешивать с Gateway sequence.
- HTTP interaction callback verification.

### Пользовательский результат

Бот может работать serverless или через HTTPS callbacks без постоянного WebSocket и без
потери событий.

## Этап 23. OAuth2 и installations

**Ветка:** `feature/oauth2`

### Операции

- authorization review/approve;
- token exchange/refresh;
- revoke/introspect/@me;
- own installations list/narrow/revoke;
- OAuth user/profile/communities;
- developer OAuth settings/secrets в отдельном client.

### Задачи

- Authorization Code + PKCE S256.
- State validation helper.
- Refresh rotation и reuse revocation.
- Client Credentials.
- Scope model без неизвестных-value crash.
- Token storage protocol, без небезопасного default файла.
- Exact redirect URI.
- `OAuthClient` отделён от Bot client.
- USER/COMMUNITY grants.
- Narrow scopes, revoke, consent changes.
- Никогда не логировать code/secret/token.

### Пользовательский результат

Можно создавать пользовательские приложения и безопасно получать разрешённый доступ без
передачи пароля VoiceRoute.

## Этап 24. Private applications и application DM

**Ветка:** `feature/private-applications`

### Операции

- private command discovery/invocation;
- private component/modal interactions;
- application DM open/get;
- DM message CRUD;
- privacy get/set;
- data deletion;
- application/user installation lifecycle.

### Задачи

- Optional bot identity.
- Separate application author.
- BOT_DM и PRIVATE_CHANNEL contexts.
- Ephemeral reply rules.
- Block/revoke behavior.
- Data deletion event workflow и ACK.
- No arbitrary personal/group chat reading.
- Private media capability guard.
- Redaction after consent loss.

### Пользовательский результат

Приложение может работать в личном контексте пользователя с явным consent и privacy
controls.

## Этап 25. Application metadata, branding и developer teams

**Ветка:** `feature/developer-client`

### Операции

- developer application list/create/update;
- metadata/profile/assets;
- branding upload/delete;
- team read/invite/cancel/change/remove/ownership;
- application invitations accept/decline;
- application audit;
- bot credentials list/rotate/revoke;
- platform intents settings/diagnostics;
- OAuth secrets;
- signing key rotation.

### Задачи

- Отдельный `DeveloperClient` и auth boundary.
- Не принимать username/password как shortcut.
- MFA-required errors.
- One-time secret wrapper с redacted repr.
- Credential grace rotation.
- ETag/idempotency.
- Team role enum и 2FA constraints.
- Application audit pagination.
- Branding upload через files pipeline.
- Profile support/privacy/terms/deletion URLs.

### Пользовательский результат

Разработчик может автоматизировать безопасные операции жизненного цикла приложения без
смешивания их с runtime бота.

## Этап 26. Presence и activities

**Ветка:** `feature/bot-presence`

### Задачи

- Typed status `online/idle/dnd/invisible`.
- До четырёх activities.
- Opcode 3 rate limiting.
- Aggregate нескольких Gateway sessions.
- Auto offline semantics.
- Presence event/cache.
- Context manager для temporary activity.
- Не путать human presence и bot presence.

### Пользовательский результат

Бот показывает актуальный статус и активность, согласованные между shards/processes.

## Этап 27. Voice state и PCM adapter

**Ветка:** `feature/voice-adapter`

### Предусловие

Реализация запускается только после проверки runtime `voiceTransport=true`. При false API
остаётся доступным как typed capability/error, но media connection не открывается.

### Операции

- voice policy get/update;
- voice states list;
- Gateway opcode 4;
- VOICE_STATE/VOICE_SERVER/RECEIVE events.

### Задачи

- Voice scopes/intents/permissions validation.
- Join/disconnect/self mute/self deafen.
- Short-lived media credential.
- LiveKit optional dependency extra.
- PCM S16LE 48 kHz mono 20 ms frames.
- Controlled receive WebSocket.
- Bounded audio queues/drop policy.
- Track mapping.
- Receive/transmit/revoke.
- Admin receive policy и privacy metadata.
- Stage audience/speaker transitions.
- Server mute/deafen.
- Reconnect without leaking token.
- No video/data-channel claims.

### Пользовательский результат

При включённой серверной возможности Python-бот может передавать и получать разрешённый
аудиопоток с явными privacy constraints.

## Этап 28. Legacy supplemental domains

**Ветка:** `feature/legacy-supplemental-api`

### Задачи

Покрыть bot-compatible функции, которые ещё отсутствуют в v1 OpenAPI, но доступны в
legacy API:

- pins/search/reaction mutations, если нет v1 equivalent;
- invites;
- forum settings;
- stage management;
- soundboard resources/play/events;
- legacy community update;
- оставшиеся moderation endpoints;
- music API только если оно официально объявлено bot-compatible и стабильно;
- любые новые legacy-only routes после автоматической классификации.

Каждый метод маркируется `legacy_only`, проверяет capability/availability и имеет
документированный путь миграции.

### Пользовательский результат

Пользователь получает максимально полное покрытие текущего VoiceRoute, не выдавая legacy
маршрут за стабильный v1-контракт.

## Этап 29. Sandbox и testing toolkit

**Ветка:** `feature/testing-toolkit`

### Операции

- sandbox runs list/create/delete;
- simulate events;
- fault injection.

### Задачи

- Capability guard `sandbox`.
- `MockVoiceRouteTransport`.
- Factories для всех domain events.
- HTTP/Gateway record-replay без credentials.
- Fake clock и deterministic retries.
- Command/interaction test harness.
- State cache assertions.
- Signature fixtures.
- Fault plans 429/503/delay/reconnect.
- pytest plugin как optional extra.

### Пользовательский результат

Бота можно полноценно тестировать локально без production community и реальных
пользователей.

## Этап 30. Background tasks, schedulers и framework ergonomics

**Ветка:** `feature/framework-runtime`

### Задачи

- `tasks.loop`-подобный decorator.
- Startup/shutdown hooks.
- Supervised tasks с restart policy.
- Cancellation and timeout scopes.
- Dependency injection для commands/listeners.
- Cogs/extensions с typed setup/teardown.
- Global and local error handlers.
- Distributed cooldown/concurrency adapters.
- Redis backend optional.
- Localization helpers.
- Help command и command tree introspection.
- Observability hooks.

### Пользовательский результат

Библиотека становится фреймворком, а не набором HTTP wrappers.

## Этап 31. Mini Apps readiness

**Ветка:** `feature/mini-apps-client`

Этот этап не начинается, пока сервер не публикует Mini Apps в OpenAPI/AsyncAPI и runtime
capabilities. Контракт реализации описан в `docs/voiceroute-mini-apps-spec.md`.

### После появления server contract

- launch/session models;
- MiniApp credential auth;
- shared state/actions;
- Mini App events;
- bot-side action handlers;
- state publish/conflict helpers;
- Python backend verification helpers;
- conformance fixtures;
- пример, не привязанный к одному типу бота.

### Пользовательский результат

Python-бот одновременно управляется командами и встроенным web UI с общим state.

## Этап 32. Документация и примеры по вертикальным сценариям

**Ветка:** `docs/complete-guide`

### Обязательные guides

- первый Gateway-бот;
- commands + autocomplete;
- components + modal;
- member join и welcome;
- role automation;
- moderation + audit;
- files + rich messages;
- polls;
- threads/support workflow;
- AutoMod;
- webhook integration;
- durable HTTPS delivery;
- OAuth user application;
- application DM;
- sharding/multi-process;
- state cache and reconciliation;
- deployment and graceful shutdown;
- testing without live server;
- voice, только при production capability;
- migration legacy SSE -> Gateway.

Каждый пример:

- запускается в CI;
- не содержит токен;
- использует `.env.example`;
- показывает permissions/intents;
- обрабатывает ошибки;
- корректно закрывает client;
- не требует hardcoded community/channel ID там, где Gateway их предоставляет.

## Этап 33. Performance, security и production hardening

**Ветка:** `perf/runtime-hardening`

### Задачи

- Memory benchmarks для cache/event queue.
- 100/1000 simulated Gateway sessions в integration harness.
- Slow handler/backpressure tests.
- File streaming benchmarks.
- Fuzz JSON/SSE/Gateway frames.
- SSRF/redirect/origin tests.
- Secret scanning и redacted repr audit.
- Cancellation leaks.
- Task/socket/file descriptor leak checks.
- Python 3.11/3.12/3.13/3.14 compatibility.
- uvloop optional verification.
- Windows/macOS/Linux.
- Packaging/sdist/wheel/import time.

### Пользовательский результат

SDK предсказуемо работает в долгоживущих production-процессах.

## Этап 34. Стабилизация публичного API и релиз 1.0

**Ветка:** `refactor/public-api-stability`

### Задачи

- Полный public symbol inventory.
- Semantic versioning policy.
- Deprecation decorators/warnings.
- Upgrade guide с `0.x`.
- API reference из docstrings.
- Проверка type-check examples.
- `py.typed`.
- Changelog automation.
- Security policy.
- Support matrix server API/package/Python.
- Release candidates.
- TestPyPI и затем PyPI.
- Signed artifacts/provenance, если инфраструктура позволяет.

### Критерий 1.0

- 100% классификация 213 исходных operations плюс новых upstream operations.
- 100% typed parsing всех advertised events.
- Нет непреднамеренных публичных `dict[str, Any]` там, где схема стабильна.
- Все examples проходят.
- Полная CI matrix зелёная.
- Нет известных secret leaks или unsafe retry.
- Legacy compatibility policy опубликована.
- Документация соответствует runtime capabilities.

---

# Матрица зависимостей

| Домен | Зависит от |
| --- | --- |
| Любой v1 API | Этапы 0–2 |
| Gateway events | Этапы 3–4 |
| State/cache objects | Этапы 4–5 |
| Commands/interactions | Этапы 2, 7–8 |
| Permissions/resources | Этапы 2, 9 |
| Rich messages | Этапы 2, 8, 13 |
| Attachments | Этапы 1–2, 14 |
| Polls | Этапы 4, 13, 16 |
| Threads | Этапы 4, 9, 13–14, 17 |
| Expressions | Этапы 14, 18 |
| AutoMod | Этапы 4, 9–10, 20 |
| Webhooks | Этапы 13–14, 21 |
| Durable delivery | Этапы 1–4, 22 |
| OAuth/private apps | Этапы 1–2, 8, 23–24 |
| Voice | Этапы 3–5, 9–10, 27 |
| Mini Apps | Серверный контракт + этапы 1–5, 8, 22 |
| Release 1.0 | Все применимые этапы |

# Рекомендуемый порядок ближайших веток

С учётом уже реализованного Gateway ближайшая практическая последовательность:

1. `chore/platform-contract-baseline`;
2. `feature/v1-http-transport`;
3. `feature/generated-models`;
4. `feature/gateway-runtime`;
5. `feature/event-catalog`;
6. `feature/domain-cache`;
7. `feature/v1-application-commands`;
8. `feature/rich-interactions`;
9. `feature/v1-permissions`;
10. `feature/v1-members`;
11. `feature/v1-roles`;
12. `feature/v1-channel-management`;
13. `feature/v1-messages`;
14. `feature/files-and-uploads`;
15. `feature/message-signals`;
16. `feature/polls`;
17. `feature/v1-threads`;
18. `feature/expressions`;
19. `feature/v1-moderation`;
20. `feature/automod-rules`;
21. `feature/message-webhooks`;
22. `feature/durable-delivery`;
23. `feature/oauth2`;
24. `feature/private-applications`;
25. `feature/developer-client`;
26. `feature/bot-presence`;
27. `feature/voice-adapter`, только после capability;
28. `feature/legacy-supplemental-api`;
29. `feature/testing-toolkit`;
30. `feature/framework-runtime`;
31. `feature/mini-apps-client`, только после server contract;
32. hardening, полная документация и 1.0.

# Definition of Done для каждой ветки

Перед merge обязательны:

```bash
.venv/bin/ruff check src tests examples
.venv/bin/ruff format --check src tests examples
.venv/bin/mypy src examples
.venv/bin/pytest
git diff --check
```

Дополнительно по домену:

- contract fixtures;
- unknown-field test;
- sequence/version > 2^53 test;
- cancellation test;
- auth boundary test;
- capability-off test;
- rate-limit/retry test для сетевых операций;
- docs/example;
- public export review;
- backward compatibility check.

# Правило обновления плана

При каждом upstream изменении VoiceRoute:

1. Обновить snapshots спецификаций отдельным commit.
2. Запустить coverage generator.
3. Классифицировать новые/изменённые/удалённые operations и events.
4. Не менять вручную generated coverage.
5. Создать отдельный migration task для breaking schema.
6. Обновить support matrix.
7. Не объявлять feature готовой до проверки runtime capabilities.

# Итоговая стратегия

Работа продолжается снизу вверх:

```text
контракты
  -> transport/errors/idempotency
  -> generated wire models
  -> Gateway/events/cache
  -> resources and interactions
  -> content/files/threads
  -> delivery/OAuth/private contexts
  -> voice and future Mini Apps
  -> framework ergonomics
  -> hardening and 1.0
```

Такой порядок минимизирует повторную переработку. Пользовательские domain APIs строятся
только после устойчивого transport и wire contracts, а high-level framework опирается на
уже проверенные resource models. В результате `voiceroute.py` будет не тонкой обёрткой над
endpoint’ами, а полноценным Python-фреймворком для всей доступной платформы VoiceRoute.
