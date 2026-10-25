# Техническое задание: полноценная платформа приложений и ботов VoiceRoute

## 1. Назначение документа

Этот документ описывает требования к развитию серверного API, realtime-инфраструктуры,
клиентов и кабинета разработчика [VoiceRoute](https://voiceroute.cc), необходимые для
создания многоуровневых сторонних ботов и приложений уровня Discord и выше.

ТЗ предназначено для владельца и разработчиков VoiceRoute. Оно описывает изменения
самого сервиса. Возможности Python-библиотеки `voiceroute.py` рассматриваются только как
потребитель будущего контракта и не могут заменить отсутствующую серверную функциональность.

Документ составлен на основании текущих материалов:

- `bots.md` — bot token, установки, базовые методы и channel SSE;
- `docs/api-methods.md` — реестр HTTP endpoints;
- `docs/api.md` — общий HTTP-контракт;
- документация форумов, модерации, сцен, soundboard, файлов и медиа;
- фактические потребности SDK и production-ботов.

## 2. Цель

Создать безопасную, версионированную и горизонтально масштабируемую платформу приложений,
которая позволяет:

1. устанавливать приложение в сообщество или пользователю;
2. получать только явно разрешённые события;
3. регистрировать нативные команды и интерактивный UI;
4. надёжно обрабатывать события после reconnect и сбоев;
5. работать в тысячах сообществ и нескольких процессах;
6. подключать ботов к голосовым каналам;
7. управлять приложением через OAuth2 и кабинет разработчика;
8. строить SDK без догадок о форматах и поведении сервера;
9. диагностировать доставку, rate limits и ошибки;
10. сохранять обратную совместимость с существующими ботами на период миграции.

## 3. Термины

| Термин | Значение |
| --- | --- |
| Application | Зарегистрированное стороннее приложение разработчика |
| Bot user | Сервисный пользователь приложения, аутентифицируемый bot token |
| Installation | Выданное приложению разрешение работать в сообществе или от имени пользователя |
| Gateway | Долгоживущее WebSocket-соединение для событий и управляющих команд |
| Intent | Категория событий, на которую приложение явно подписывается |
| Interaction | Серверный вызов команды, компонента, autocomplete или modal submit |
| Event sequence | Монотонная позиция события внутри Gateway session/shard |
| Delivery ID | Уникальный идентификатор конкретной доставки события |
| Idempotency key | Идентификатор логической изменяющей операции, устойчивый к повторам |
| Scope | OAuth2-возможность, выданная пользователем приложению |
| Permission | Право участника или bot user внутри сообщества/канала |
| Shard | Независимая часть Gateway-сессии, обслуживающая подмножество сообществ |

## 4. Границы проекта

### 4.1. Входит в объём

- Gateway и полная модель событий;
- intents и privileged intents;
- application commands и interactions;
- message components и modals;
- OAuth2, scopes и установки;
- DM/user installations;
- bot presence;
- публичный voice transport;
- расширение REST API;
- версионирование, OpenAPI и AsyncAPI;
- эксплуатация, sharding, rate limits и observability;
- developer portal;
- миграция текущих SSE-ботов.

### 4.2. Не входит в первую поставку

- монетизация приложений;
- магазин цифровых товаров;
- игровая overlay-система;
- собственный SFU вместо текущего медиастека;
- выполнение произвольного кода ботов на инфраструктуре VoiceRoute;
- полная копия всех продуктовых функций Discord.

Эти возможности допускаются после стабилизации публичной платформы.

## 5. Основные архитектурные принципы

1. **At-least-once delivery.** Событие может прийти повторно. Каждое событие обязано иметь
   стабильный ID, позволяющий дедупликацию.
2. **Idempotency by design.** Все критичные mutation endpoints принимают idempotency key.
3. **Least privilege.** OAuth scopes, intents и community permissions являются разными
   слоями контроля и проверяются независимо.
4. **Versioned contracts.** Любой публичный JSON payload имеет документированную версию.
5. **Unknown-field tolerance.** Добавление необязательного поля не является breaking change.
6. **No secrets in URLs.** Bot token, OAuth token и interaction secret не передаются в query.
7. **No process-local correctness.** Лимиты, сессии, replay и идемпотентность работают при
   нескольких экземплярах API.
8. **Observable delivery.** Каждый запрос и событие имеют request/delivery/trace ID.
9. **Explicit lifecycle.** Установка, отзыв доступа, reconnect и graceful shutdown являются
   частью протокола, а не неявным поведением SDK.
10. **Backward-compatible migration.** Legacy SSE поддерживается до завершения объявленного
    срока миграции.

---

# Часть I. Версионирование и общие HTTP-контракты

## 6. Версия API

Новые endpoints публикуются под префиксом:

```text
/api/v1/...
```

Существующие `/api/...` считаются legacy contract. Их нельзя молча менять под видом v1.

Ответ должен содержать:

```http
X-VoiceRoute-API-Version: 1
X-Request-ID: 01J...
```

Для deprecated endpoint:

```http
Deprecation: true
Sunset: Wed, 01 Jul 2028 00:00:00 GMT
Link: <https://docs.voiceroute.cc/migrations/...>; rel="deprecation"
```

### Критерии приёмки

- версия отражена в OpenAPI;
- legacy и v1 могут работать одновременно;
- CI отклоняет несовместимое изменение schema без явного major version;
- опубликована политика совместимости и срок поддержки версий.

## 7. Единый формат ошибок

Все v1 endpoints возвращают:

```json
{
  "error": {
    "code": "MISSING_PERMISSION",
    "message": "Application cannot send messages in this channel",
    "requestId": "01JABC...",
    "retryable": false,
    "details": {
      "permission": "sendMessages",
      "resourceType": "channel",
      "resourceId": "..."
    },
    "fieldErrors": []
  }
}
```

`fieldErrors`:

```json
[
  {
    "pointer": "/options/0/name",
    "code": "INVALID_FORMAT",
    "message": "Name must contain 1-32 characters"
  }
]
```

Обязательные правила:

- `code` стабилен и не локализуется;
- `message` предназначен для разработчика, а не для прямого показа пользователю;
- `requestId` также возвращается заголовком;
- `retryable` однозначно определяет допустимость автоматического повтора;
- `429` содержит `retryAfterMs`;
- `409` по возможности содержит текущую версию ресурса;
- `403` может содержать недостающее scope/permission без раскрытия закрытого объекта;
- `404` сохраняет privacy semantics для скрытых ресурсов.

## 8. Idempotency

Все создающие и критичные изменяющие операции принимают:

```http
Idempotency-Key: <UUID или ULID>
```

Сервер хранит результат не менее 24 часов в области:

```text
application + installation + method + canonical route + key
```

Повтор идентичной операции возвращает исходный результат и:

```http
Idempotency-Replayed: true
```

Повтор с другим телом возвращает `409 IDEMPOTENCY_KEY_REUSED`.

`clientMessageId` сохраняется ради совместимости, но новый общий механизм должен работать
для сообщений, moderation actions, command registration и webhook operations.

## 9. Pagination

Для всех больших коллекций используется cursor pagination:

```json
{
  "items": [],
  "page": {
    "nextCursor": "opaque-or-null",
    "hasMore": false
  }
}
```

Требования:

- cursor непрозрачен;
- нельзя требовать преобразования bigint в JavaScript Number;
- порядок документирован и стабилен внутри прохода;
- `limit` имеет серверное максимальное значение;
- invalid/expired cursor возвращает отдельный error code;
- offset pagination не используется для изменяемых больших коллекций.

## 10. Optimistic concurrency

Настройки приложения, команды, каналы, роли, AutoMod и forum settings имеют `version` или
`ETag`.

Mutation использует:

```http
If-Match: "resource-version"
```

При конфликте сервер возвращает `409 RESOURCE_VERSION_CONFLICT` и текущий ETag.

---

# Часть II. Gateway и доставка событий

## 11. Gateway endpoint

```http
GET /api/v1/gateway
Authorization: Bot <token>
```

Ответ:

```json
{
  "url": "wss://gateway.voiceroute.cc/v1",
  "recommendedShards": 1,
  "sessionStartLimit": {
    "total": 1000,
    "remaining": 999,
    "resetAfterMs": 86400000,
    "maxConcurrency": 1
  }
}
```

WebSocket query может содержать только несекретные параметры:

```text
wss://gateway.voiceroute.cc/v1?version=1&encoding=json&compress=zstd-stream
```

## 12. Gateway envelope

Каждый frame:

```json
{
  "op": 0,
  "event": "MESSAGE_CREATED",
  "sequence": "18446744073709551616",
  "data": {},
  "deliveryId": "01J...",
  "occurredAt": "2026-10-25T12:34:56.789Z",
  "traceId": "01J...",
  "schemaVersion": 1
}
```

`sequence` передаётся строкой. `deliveryId` уникален для логического события и остаётся
стабильным при replay.

### Минимальный набор opcodes

| Opcode | Имя | Направление |
| --- | --- | --- |
| 0 | DISPATCH | server → client |
| 1 | HEARTBEAT | client → server |
| 2 | IDENTIFY | client → server |
| 3 | PRESENCE_UPDATE | client → server |
| 6 | RESUME | client → server |
| 7 | RECONNECT | server → client |
| 9 | INVALID_SESSION | server → client |
| 10 | HELLO | server → client |
| 11 | HEARTBEAT_ACK | server → client |
| 12 | SUBSCRIPTION_UPDATE | client → server |
| 13 | ACK | client → server, опционально для durable mode |

Числа могут отличаться, но после публикации не переиспользуются.

## 13. Identify

```json
{
  "op": 2,
  "data": {
    "token": "vrb_...",
    "intents": ["communities", "messages", "messageContent"],
    "properties": {
      "os": "linux",
      "library": "voiceroute.py",
      "libraryVersion": "0.2.0"
    },
    "shard": [0, 4],
    "presence": {
      "status": "online",
      "activities": []
    }
  }
}
```

Токен допускается только в первом Identify frame поверх TLS и никогда не логируется.

## 14. Ready и resume

`READY`:

```json
{
  "sessionId": "opaque",
  "resumeGatewayUrl": "wss://gateway.voiceroute.cc/v1",
  "application": { "id": "..." },
  "bot": { "id": 42, "bot": true },
  "shard": [0, 1],
  "installedCommunityIds": ["..."]
}
```

`RESUME`:

```json
{
  "op": 6,
  "data": {
    "token": "vrb_...",
    "sessionId": "opaque",
    "sequence": "12345"
  }
}
```

Требования:

- replay window не менее 5 минут на первом этапе, целевой — 15 минут;
- session state находится в общем хранилище, а не памяти одного API process;
- reconnect к другому экземпляру сервера поддерживает resume;
- сервер сообщает, можно ли resume, отдельным кодом;
- после невозможного resume SDK делает новый Identify и REST reconciliation;
- повтор события после resume считается нормой.

## 15. Heartbeat и close codes

`HELLO` содержит `heartbeatIntervalMs`. Клиент отправляет heartbeat с последним sequence.
При отсутствии ACK в течение двух интервалов клиент закрывает соединение и reconnect-ится.

Нужно определить стабильные close codes минимум для:

- unknown error;
- unknown opcode;
- decode error;
- not authenticated;
- authentication failed;
- already authenticated;
- invalid sequence;
- rate limited;
- session timeout;
- invalid shard;
- sharding required;
- invalid intents;
- disallowed intents;
- token revoked;
- installation unavailable.

Для каждого кода документируется: terminal/reconnectable, нужен ли новый Identify и
минимальная задержка.

## 16. Sharding

Назначение сообщества shard-у:

```text
stable_hash(community_id) % shard_count
```

Требования:

- один community всегда принадлежит одному shard;
- direct/user-install события маршрутизируются детерминированно;
- сервер валидирует `shard_id < shard_count`;
- большие приложения обязаны использовать рекомендованное число shards;
- Identify rate limit координируется глобально;
- изменение shard count не теряет события;
- Developer Portal показывает активные sessions/shards.

## 17. Intents

Минимальный реестр:

| Intent | События | Privileged |
| --- | --- | --- |
| `communities` | community/channel/role lifecycle | Нет |
| `members` | join/update/leave, member chunks | Да для крупных приложений |
| `moderation` | bans, timeouts, AutoMod actions | Да |
| `messages` | create/update/delete без защищённого body | Нет |
| `messageContent` | body, attachments, embeds | Да |
| `reactions` | reaction lifecycle | Нет |
| `threads` | thread/forum lifecycle | Нет |
| `presence` | user presence/activity | Да |
| `voiceStates` | voice membership/state | Да |
| `interactions` | commands/components/modals | Нет |
| `webhooks` | webhook lifecycle | Нет |
| `auditLog` | новые audit entries | Да |

Правила:

- intent не выдаёт permission;
- permission не включает intent автоматически;
- отсутствующие privileged intents отклоняются при Identify;
- payload редактируется сервером: без `messageContent` body отсутствует;
- scopes/intents/permissions документируются в общей capability matrix.

## 18. Полный каталог событий v1

Минимально обязательные события:

```text
READY
RESUMED
APPLICATION_UPDATED
INSTALLATION_CREATED
INSTALLATION_UPDATED
INSTALLATION_DELETED
COMMUNITY_AVAILABLE
COMMUNITY_UNAVAILABLE
COMMUNITY_UPDATED
COMMUNITY_DELETED
CHANNEL_CREATED
CHANNEL_UPDATED
CHANNEL_DELETED
CHANNEL_ORDER_UPDATED
CHANNEL_PERMISSIONS_UPDATED
MEMBER_JOINED
MEMBER_UPDATED
MEMBER_LEFT
MEMBERS_CHUNK
ROLE_CREATED
ROLE_UPDATED
ROLE_DELETED
ROLE_ORDER_UPDATED
MESSAGE_CREATED
MESSAGE_UPDATED
MESSAGE_DELETED
MESSAGES_BULK_DELETED
MESSAGE_PINS_UPDATED
REACTION_ADDED
REACTION_REMOVED
REACTIONS_CLEARED
TYPING_STARTED
THREAD_CREATED
THREAD_UPDATED
THREAD_DELETED
THREAD_MEMBER_UPDATED
THREAD_MEMBERS_UPDATED
FORUM_UPDATED
INVITE_CREATED
INVITE_DELETED
BAN_CREATED
BAN_DELETED
TIMEOUT_UPDATED
AUTOMOD_RULE_CREATED
AUTOMOD_RULE_UPDATED
AUTOMOD_RULE_DELETED
AUTOMOD_ACTION_EXECUTED
AUDIT_LOG_ENTRY_CREATED
WEBHOOK_CREATED
WEBHOOK_UPDATED
WEBHOOK_DELETED
PRESENCE_UPDATED
VOICE_STATE_UPDATED
VOICE_SERVER_UPDATED
STAGE_UPDATED
SOUNDBOARD_PLAYED
EXPRESSION_CREATED
EXPRESSION_UPDATED
EXPRESSION_DELETED
INTERACTION_CREATED
```

Каждое событие документирует:

- required intent;
- required installation scope;
- возможные отсутствующие поля;
- ordering key;
- replay semantics;
- privacy filtering;
- пример payload;
- REST endpoint для reconciliation.

## 19. Durable event delivery «выше Discord»

Дополнительный режим для критичных интеграций:

```http
POST /api/v1/applications/{applicationId}/event-subscriptions
```

Subscription может использовать:

- WebSocket pull/session;
- подписанный HTTPS webhook;
- durable pull queue.

Настройки:

```json
{
  "transport": "webhook",
  "url": "https://bot.example/events",
  "eventTypes": ["MEMBER_JOINED", "AUTOMOD_ACTION_EXECUTED"],
  "communityIds": [],
  "maxAttempts": 12
}
```

Нужны ACK, delivery log, manual replay, dead-letter state и retention не менее 24 часов.

---

# Часть III. Application Commands и Interactions

## 20. Модель команды

Типы:

- `CHAT_INPUT`;
- `USER`;
- `MESSAGE`;
- в будущем `ACTIVITY_ENTRY_POINT`.

Command:

```json
{
  "id": "...",
  "applicationId": "...",
  "scope": { "type": "global" },
  "type": "CHAT_INPUT",
  "name": "moderate",
  "nameLocalizations": { "en": "moderate" },
  "description": "Управление модерацией",
  "descriptionLocalizations": {},
  "options": [],
  "defaultMemberPermissions": ["moderateMembers"],
  "contexts": ["COMMUNITY"],
  "nsfw": false,
  "version": "12"
}
```

## 21. Command endpoints

```text
GET    /api/v1/applications/{applicationId}/commands
POST   /api/v1/applications/{applicationId}/commands
PUT    /api/v1/applications/{applicationId}/commands
GET    /api/v1/applications/{applicationId}/commands/{commandId}
PATCH  /api/v1/applications/{applicationId}/commands/{commandId}
DELETE /api/v1/applications/{applicationId}/commands/{commandId}

GET    /api/v1/applications/{applicationId}/communities/{communityId}/commands
POST   /api/v1/applications/{applicationId}/communities/{communityId}/commands
PUT    /api/v1/applications/{applicationId}/communities/{communityId}/commands
PATCH  /api/v1/applications/{applicationId}/communities/{communityId}/commands/{commandId}
DELETE /api/v1/applications/{applicationId}/communities/{communityId}/commands/{commandId}
```

`PUT` выполняет атомарную bulk synchronization. Guild/community commands применяются сразу;
глобальные имеют version и документированное время распространения.

## 22. Typed options

Поддержать:

- `SUB_COMMAND`;
- `SUB_COMMAND_GROUP`;
- `STRING`;
- `INTEGER`;
- `NUMBER`;
- `BOOLEAN`;
- `USER`;
- `CHANNEL`;
- `ROLE`;
- `MENTIONABLE`;
- `ATTACHMENT`.

Option поддерживает:

- `name`, `description` и локализации;
- `required`;
- статические `choices`;
- `autocomplete`;
- `minValue`, `maxValue`;
- `minLength`, `maxLength`;
- `channelTypes`;
- один уровень group → subcommand;
- серверную валидацию типов до отправки interaction приложению.

## 23. Interaction payload

```json
{
  "id": "01J...",
  "applicationId": "...",
  "type": "APPLICATION_COMMAND",
  "token": "short-lived-secret",
  "version": 1,
  "communityId": "...",
  "channelId": "...",
  "member": {},
  "user": {},
  "locale": "ru",
  "communityLocale": "ru",
  "applicationPermissions": ["viewChannel", "sendMessages"],
  "data": {
    "commandId": "...",
    "name": "moderate",
    "type": "CHAT_INPUT",
    "options": [],
    "resolved": {
      "users": {},
      "members": {},
      "roles": {},
      "channels": {},
      "messages": {},
      "attachments": {}
    }
  }
}
```

Interaction token:

- используется только для ответа на конкретный interaction;
- не является bot token;
- имеет ограниченный TTL;
- не показывается в логах;
- привязан к application ID и interaction ID.

## 24. Ответы на interaction

Endpoint первичного ответа:

```text
POST /api/v1/interactions/{interactionId}/{interactionToken}/callback
```

Типы callback:

- immediate message;
- deferred message;
- deferred component update;
- update source message;
- autocomplete result;
- modal;
- pong для endpoint verification при необходимости.

Временные гарантии:

- первичный ACK — не позднее 3 секунд;
- interaction token действует минимум 15 минут для follow-up;
- deferred response показывает пользователю состояние выполнения;
- повтор callback с тем же idempotency key безопасен.

Follow-up API:

```text
GET    /api/v1/webhooks/{applicationId}/{interactionToken}/messages/@original
PATCH  /api/v1/webhooks/{applicationId}/{interactionToken}/messages/@original
DELETE /api/v1/webhooks/{applicationId}/{interactionToken}/messages/@original
POST   /api/v1/webhooks/{applicationId}/{interactionToken}
GET    /api/v1/webhooks/{applicationId}/{interactionToken}/messages/{messageId}
PATCH  /api/v1/webhooks/{applicationId}/{interactionToken}/messages/{messageId}
DELETE /api/v1/webhooks/{applicationId}/{interactionToken}/messages/{messageId}
```

## 25. Ephemeral responses

Ephemeral message:

- видит только вызвавший пользователь;
- не попадает в обычную историю канала;
- не доступен другим ботам;
- не индексируется поиском;
- имеет документированный TTL;
- может редактироваться и удаляться interaction token;
- не создаёт обычные mention notifications;
- помечается message flag `EPHEMERAL`.

## 26. Autocomplete

Клиент отправляет interaction при изменении focused option. Бот отвечает максимум
25 вариантами. Сервер:

- ограничивает частоту;
- отменяет устаревшие запросы;
- не применяет старый ответ к новому вводу;
- не логирует чувствительное содержимое;
- передаёт уже заполненные options;
- валидирует конечное значение при выполнении команды независимо от autocomplete.

## 27. Command permissions

Endpoints:

```text
GET /api/v1/applications/{applicationId}/communities/{communityId}/command-permissions
GET /api/v1/applications/{applicationId}/communities/{communityId}/commands/{commandId}/permissions
PUT /api/v1/applications/{applicationId}/communities/{communityId}/commands/{commandId}/permissions
```

Target types:

- role;
- user;
- channel;
- all members;
- all channels.

Нужна UI-страница в «Интеграции → Приложение». Пользователь без права вызвать команду не
видит её в picker.

---

# Часть IV. Components, Modals и Rich Messages

## 28. Message components

Поддержать:

- action row;
- button: primary, secondary, success, danger, link;
- string select;
- user select;
- role select;
- channel select;
- mentionable select.

Component:

```json
{
  "type": "BUTTON",
  "style": "PRIMARY",
  "label": "Подтвердить",
  "customId": "confirm:order:123",
  "emoji": null,
  "disabled": false,
  "accessibilityLabel": "Подтвердить заказ"
}
```

Ограничения длины и количества публикуются в OpenAPI. `customId` возвращается приложению
без изменений, но не должен использоваться как доверенное хранилище прав.

## 29. Modals

Modal поддерживает:

- title;
- custom ID;
- short/paragraph text input;
- required;
- min/max length;
- placeholder;
- default value;
- в следующей версии date/time, number и file input.

Modal submit создаёт отдельный interaction. Сервер проверяет, что modal был открыт тем же
приложением и пользователем и не истёк.

## 30. Rich message schema

Расширить сообщение:

```json
{
  "content": "Текст",
  "embeds": [],
  "components": [],
  "attachments": [],
  "allowedMentions": {
    "parse": [],
    "users": [],
    "roles": [],
    "repliedUser": false
  },
  "flags": [],
  "reply": { "messageId": "...", "failIfNotExists": false }
}
```

Embed поддерживает title, description, URL, color, timestamp, author, footer, fields,
thumbnail и image. Сервер обязан ограничивать общий размер и безопасно proxy-ить внешние
изображения.

Обязательные message flags:

- `EPHEMERAL`;
- `SUPPRESS_EMBEDS`;
- `SUPPRESS_NOTIFICATIONS`;
- `HAS_COMPONENTS`;
- `LOADING` для deferred interaction;
- `FAILED` для явного состояния неудачного системного ответа при необходимости.

## 31. Polls

После основного interaction milestone добавить:

- create poll;
- single/multiple choice;
- duration;
- anonymous/non-anonymous policy;
- close poll;
- poll vote events;
- permission and privacy rules;
- immutable result snapshot после завершения.

---

# Часть V. OAuth2, установки и безопасность приложений

## 32. OAuth2 endpoints

```text
GET  /oauth2/authorize
POST /api/v1/oauth2/token
POST /api/v1/oauth2/revoke
POST /api/v1/oauth2/introspect        # опционально для confidential clients
GET  /api/v1/oauth2/@me
```

Поддержать:

- Authorization Code;
- Authorization Code + PKCE S256;
- Client Credentials;
- Refresh Token;
- installation shortcut для bot/community install;
- явный запрет Resource Owner Password flow.

## 33. Scopes v1

Минимальный набор:

```text
identify
profile.read
communities.read
communities.members.read
applications.commands
applications.commands.permissions.update
bot
webhook.incoming
dm.read
dm.write
voice.connect
voice.receive
voice.transmit
```

Scopes не заменяют community permissions. Например, `voice.connect` разрешает функции
приложения в принципе, а `connectVoice` проверяет конкретный канал.

## 34. Application credentials

Application хранит:

- public client ID;
- тип public/confidential client;
- несколько redirect URIs;
- несколько active client secrets с fingerprint;
- public key для interaction signatures;
- allowed origins;
- allowed installation contexts;
- default scopes;
- default bot permissions;
- privileged intent approvals.

Требования к secret rotation:

- новый secret создаётся без мгновенного отзыва старого;
- старый можно отозвать отдельно;
- plaintext показывается один раз;
- хранится только надёжный hash/шифрованный secret в зависимости от протокола;
- UI показывает fingerprint, createdAt, lastUsedAt;
- все операции записываются в developer audit log.

Bot token также должен поддерживать zero-downtime rotation: новый и старый token могут
действовать одновременно в коротком настраиваемом grace period, после чего старый отзывается.

## 35. Installation model

```json
{
  "id": "...",
  "applicationId": "...",
  "type": "COMMUNITY",
  "ownerUserId": 123,
  "communityId": "...",
  "scopes": ["bot", "applications.commands"],
  "permissions": ["viewChannel", "sendMessages"],
  "createdAt": "...",
  "updatedAt": "...",
  "revokedAt": null
}
```

Типы установки:

- `COMMUNITY`;
- `USER`.

Нужно поддержать приложение без bot user, если ему достаточно interactions.

## 36. Consent и повышение прав

- экран показывает приложение, владельца, scopes и community permissions;
- опасные права выделяются отдельно;
- изменение manifest не повышает старые установки автоматически;
- приложение получает событие об изменении grants;
- пользователь может отозвать отдельный scope/установку;
- повышение требует нового consent;
- `state` обязателен для browser OAuth;
- redirect URI сравнивается полностью;
- PKCE обязателен для public clients.

## 37. User-installed apps и DM

Нужно добавить:

- установку приложения пользователем;
- команды в `BOT_DM` и `PRIVATE_CHANNEL` contexts;
- создание/получение DM между пользователем и приложением;
- interaction-only режим без постоянного DM;
- блокировку приложения пользователем;
- удаление истории в рамках продуктовой политики;
- события DM только при явном scope;
- запрет ботам читать личные/групповые чаты без конкретной установки и consent;
- uninstall callback/event;
- endpoint удаления пользовательских данных приложения.

## 38. Подписи interaction/webhook

HTTP interactions и event webhooks подписываются Ed25519 либо эквивалентной схемой.

Заголовки:

```http
X-VoiceRoute-Signature: ...
X-VoiceRoute-Timestamp: ...
X-VoiceRoute-Delivery-ID: ...
```

Получатель обязан проверять подпись и допустимое отклонение времени. Повтор одного delivery
ID безопасно игнорируется.

---

# Часть VI. Presence и Voice API

## 39. Bot presence

Gateway-команда позволяет установить:

```json
{
  "op": 3,
  "data": {
    "status": "online",
    "since": null,
    "activities": [
      {
        "type": "CUSTOM",
        "name": "Помогаю сообществу"
      }
    ]
  }
}
```

Статусы: `online`, `idle`, `dnd`, `invisible`.

Требования:

- presence связано с живой Gateway session;
- отсутствие всех sessions делает бота offline после grace period;
- status агрегируется между shards;
- rate limit обновлений documented;
- `lastUsedAt` не используется как presence;
- клиент различает offline и degraded/unavailable при системной возможности.

## 40. Voice handshake

Для подключения стороннего бота:

1. бот отправляет Gateway voice state update с `communityId`, `channelId`;
2. получает `VOICE_STATE_UPDATED` с session ID;
3. получает `VOICE_SERVER_UPDATED` с endpoint и краткоживущим media token;
4. подключается к media transport;
5. выполняет media protocol handshake;
6. публикует/получает разрешённые tracks.

Bot token не передаётся медиасерверу. Используется отдельный короткоживущий credential.

## 41. Voice capabilities

Минимум:

- connect/disconnect/move;
- receive audio;
- transmit audio;
- self mute/deafen;
- server mute/deafen events;
- speaking events;
- participant/track mapping;
- Opus frames или официальный PCM abstraction;
- reconnect/resume;
- TURN/TCP fallback;
- stage audience/speaker mode;
- ограничение количества voice sessions;
- permissions `connectVoice`, `speak`, `listen`, `stream`, `useSoundboard`;
- отдельные scopes `voice.connect`, `voice.receive`, `voice.transmit`;
- observability join → token → transport → first audio;
- токены и аудиоданные не попадают в логи.

## 42. Приватность голоса

- получение аудио требует отдельного scope и permission;
- UI явно показывает присутствие recording/transcription bot;
- сервер публикует событие о начале/окончании записи;
- администратор может запретить voice receive для приложений;
- политика хранения аудио указывается в приложении;
- приложение предоставляет privacy policy и deletion endpoint;
- запрещено выдавать старые media credentials после revoke/ban/kick;
- необходимо проверить строгий revoke уже выданных media tokens.

---

# Часть VII. Расширение REST ресурсов

## 43. Сообщения

Добавить/нормализовать:

```text
GET    /api/v1/communities/{communityId}/channels/{channelId}/messages/{messageId}
POST   /api/v1/communities/{communityId}/channels/{channelId}/messages
PATCH  /api/v1/communities/{communityId}/channels/{channelId}/messages/{messageId}
DELETE /api/v1/communities/{communityId}/channels/{channelId}/messages/{messageId}
POST   /api/v1/communities/{communityId}/channels/{channelId}/messages/bulk-delete
```

Требования:

- отдельный глобально уникальный `messageId`;
- `seq` сохраняется как ordering cursor;
- allowed mentions;
- embeds/components;
- attachment lifecycle;
- reasoned moderation delete;
- bulk delete с частичными ошибками или атомарной семантикой;
- отдельные create/update/delete events;
- author/webhook/application attribution;
- snapshot reply даже при удалении исходного сообщения согласно политике приватности.

## 44. Участники

```text
GET   /api/v1/communities/{communityId}/members/{userId}
GET   /api/v1/communities/{communityId}/members?cursor=&limit=
GET   /api/v1/communities/{communityId}/members/search?query=&cursor=
PATCH /api/v1/communities/{communityId}/members/{userId}
PUT   /api/v1/communities/{communityId}/members/{userId}/roles/{roleId}
DELETE /api/v1/communities/{communityId}/members/{userId}/roles/{roleId}
```

Добавить chunking для Gateway, join timestamp, pending state, nickname, roles, timeout,
effective permissions и voice state reference.

## 45. Каналы и категории

Добавить:

- `GET` отдельного канала;
- `DELETE` канала;
- channel clone;
- типизированные settings по channel kind;
- атомарное изменение порядка;
- archived thread listings;
- private thread membership;
- channel version/ETag;
- события всех изменений;
- reason header для административных операций.

## 46. Роли

Добавить:

- получение отдельной роли;
- атомарное изменение порядка;
- idempotent add/remove member role;
- icon/unicode emoji;
- managed/application metadata;
- versioned permission registry;
- события порядка и назначения;
- effective permission endpoint;
- permission simulation/dry run.

## 47. Expressions, emoji и stickers

Разделить типы в публичной схеме. Для каждого объекта нужны:

- create/get/list/update/delete;
- name;
- creator;
- format/MIME;
- animated;
- available;
- role restrictions;
- size limits;
- content validation;
- events create/update/delete;
- CDN/file URL contract.

## 48. AutoMod

Вместо одного агрегированного settings объекта предусмотреть rules:

```text
GET    /api/v1/communities/{communityId}/automod/rules
POST   /api/v1/communities/{communityId}/automod/rules
GET    /api/v1/communities/{communityId}/automod/rules/{ruleId}
PATCH  /api/v1/communities/{communityId}/automod/rules/{ruleId}
DELETE /api/v1/communities/{communityId}/automod/rules/{ruleId}
```

Triggers: keywords, presets, regex, mention spam, link/domain policy.

Actions: block, alert channel, timeout. Поддержать exempt roles/channels и событие
`AUTOMOD_ACTION_EXECUTED`.

## 49. Webhooks

Message webhook API расширить:

- get/update/delete;
- rotate secret с grace period;
- execute with `wait=true`;
- edit/delete webhook message;
- embeds/components/attachments;
- username/avatar override по политике;
- thread target;
- idempotency;
- attribution application/webhook.

Event webhooks являются отдельным объектом и не используют secret URL message webhook-а.

## 50. Файлы

Ввести upload session:

```text
POST /api/v1/uploads
PUT  /api/v1/uploads/{uploadId}/parts/{partNumber}
POST /api/v1/uploads/{uploadId}/complete
GET  /api/v1/uploads/{uploadId}
DELETE /api/v1/uploads/{uploadId}
```

Статусы: `pending`, `uploading`, `scanning`, `ready`, `rejected`, `expired`.

Нужны checksum, resumable upload, quota, MIME по содержимому, attachment description,
spoiler flag, thumbnail metadata, range download и событие scan completion.

---

# Часть VIII. Rate limits, безопасность и эксплуатация

## 51. Rate-limit headers

Каждый ограничиваемый endpoint возвращает:

```http
X-RateLimit-Limit: 50
X-RateLimit-Remaining: 49
X-RateLimit-Reset-After: 1.000
X-RateLimit-Bucket: opaque
X-RateLimit-Scope: bot
```

`429`:

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests",
    "requestId": "...",
    "retryable": true,
    "details": {
      "retryAfterMs": 1000,
      "global": false,
      "bucket": "opaque"
    }
  }
}
```

Лимиты должны храниться в общем хранилище либо вычисляться так, чтобы несколько API
instances применяли единый результат.

## 52. Security requirements

- bot/OAuth/interaction/media secrets редактируются во всех логах;
- токен не принимается в query/cookie;
- секретные ответы имеют `Cache-Control: no-store`;
- token rotation и revoke распространяются между instances;
- активные Gateway sessions закрываются при revoke;
- interaction/webhook подписи защищены от replay;
- login и developer-sensitive operations требуют 2FA согласно текущей политике;
- developer team actions попадают в отдельный audit log;
- SSRF-защита внешних media/embed URL;
- malware scanner fail-closed для публикации файлов;
- dependency/security scanning в CI;
- documented vulnerability disclosure;
- автоматическое обнаружение bot token в публичном Git по возможности;
- per-installation data deletion hook;
- privacy manifest приложения.

## 53. Event infrastructure

Рекомендуемая схема:

```text
PostgreSQL transaction
    -> transactional outbox
        -> event dispatcher
            -> Gateway session store
            -> webhook delivery queue
            -> durable replay storage
```

Требования:

- событие создаётся в той же транзакции, что и domain mutation;
- outbox publication идемпотентна;
- consumer deduplicates event ID;
- порядок гарантируется минимум в пределах community/resource key;
- сбой отдельного consumer не блокирует API mutation;
- retry не удерживает DB transaction;
- delivery backlog наблюдаем;
- retention и purge документированы.

## 54. Horizontal scaling

- sessions и rate limits не process-local;
- Gateway может принять resume на другом node;
- graceful drain при deploy;
- load balancer не требует вечной sticky session;
- worker leadership использует lease/lock;
- все background jobs идемпотентны;
- music/stateful services либо переносятся в shared state, либо явно остаются вне public bot contract;
- readiness проверяет DB, event broker и обязательные зависимости;
- liveness не выдаётся за функциональную готовность.

## 55. Observability

Обязательные метрики:

- active Gateway sessions/shards;
- Identify/Resume success rate;
- heartbeat latency;
- event publish-to-delivery latency;
- replay count;
- duplicate delivery count;
- delivery backlog age/size;
- webhook attempts/failures;
- REST latency/error/rate-limit count;
- interaction ACK latency и missed deadline;
- voice join/token/first-audio latency;
- attachment scan latency;
- OAuth authorization/token failures.

Логи структурированные и содержат request ID, trace ID, application ID и installation ID,
но не содержат tokens, message content и аудиоданные по умолчанию.

## 56. Developer status and diagnostics

Developer Portal показывает:

- активные installations;
- Gateway sessions/shards;
- последние disconnect codes;
- event delivery latency;
- webhook delivery log;
- replay кнопка;
- rate-limit usage;
- interaction latency/error rate;
- token/secret fingerprints и last used;
- privileged intent status;
- API version compatibility;
- system status и incidents.

---

# Часть IX. Developer Portal

## 57. Application settings

Добавить разделы:

1. General information: name, description, icon, banner, support/privacy/terms URLs.
2. Installation: contexts, scopes, default permissions, install URL.
3. OAuth2: client type, secrets, redirect URIs, allowed origins.
4. Bot: token management, presence defaults, public/private, intents.
5. Commands: зарегистрированные global/community commands.
6. Interactions: public key, HTTP endpoint или Gateway delivery.
7. Event subscriptions: Gateway/webhook/durable subscriptions.
8. Webhooks: endpoints, secret rotation, delivery logs.
9. Team: owners, developers, analysts, security roles.
10. Analytics: installs, commands, events, failures and latency.
11. Audit: immutable developer administration history.
12. Verification: requested privileged capabilities and review state.

## 58. Application teams

Роли:

- owner;
- administrator;
- developer;
- security manager;
- analyst/read-only.

Требования:

- передача ownership;
- обязательная 2FA для sensitive roles;
- revoke всех sessions участника после удаления из команды;
- audit каждого изменения;
- нельзя оставить приложение без owner;
- production secrets недоступны analyst.

## 59. Verification and catalog

Для публичного каталога:

- verified owner/team;
- privacy policy;
- terms;
- support contact;
- permission justification;
- privileged intent review;
- security review для voice/message-content at scale;
- install count thresholds;
- report application;
- disable/quarantine flow;
- version/release notes;
- категории и поиск;
- метрики качества без публикации секретной аналитики.

---

# Часть X. Документация и SDK contract

## 60. OpenAPI

Публиковать machine-readable OpenAPI 3.1:

```text
GET /api/v1/openapi.json
```

Спецификация включает:

- schemas;
- enums;
- security schemes;
- errors;
- pagination;
- rate-limit headers;
- idempotency;
- examples;
- deprecation metadata.

CI выполняет schema diff и блокирует undocumented endpoint.

## 61. AsyncAPI

Gateway и webhook events описываются AsyncAPI:

```text
GET /api/v1/asyncapi.json
```

Для каждого события указаны intents, scopes, permissions, ordering key и replay behavior.

## 62. Capability discovery

```text
GET /api/v1/capabilities
```

Ответ показывает:

- API/Gateway versions;
- поддерживаемые intents;
- event types;
- command/component types;
- voice capabilities;
- upload limits;
- global limits;
- deprecated features.

Это особенно важно для dev/prod, которые могут обновляться в разное время.

## 63. SDK conformance suite

VoiceRoute предоставляет language-neutral набор fixtures:

- HTTP request/response cases;
- Gateway frames;
- reconnect/resume sequences;
- duplicated/out-of-order events;
- rate limits;
- interaction callbacks;
- signature verification vectors;
- OAuth PKCE vectors;
- voice handshake fixtures без реального аудио;
- unknown enum/field compatibility.

SDK может публиковать badge совместимости с конкретной версией API.

## 64. Sandbox

Необходимо оставить изолированные dev/prod credentials и добавить:

- тестовые applications;
- тестовую community installation;
- event simulator;
- interaction simulator;
- webhook test delivery;
- synthetic members/messages;
- controlled error/rate-limit injection;
- replay конкретного события;
- очистку sandbox data;
- запрет переноса токенов между environments.

---

# Часть XI. Миграция существующего API

## 65. Совместимость

Нельзя немедленно удалять:

- `Authorization: Bot`;
- текущий `/api/bots/@me`;
- `GET /api/communities`;
- channel message history/send;
- channel SSE;
- `clientMessageId`.

Они работают в legacy mode до объявленного sunset.

## 66. Этапы миграции

### Этап A — спецификация и foundation

- утвердить v1 error schema;
- OpenAPI;
- idempotency middleware;
- shared rate limiter;
- request/trace IDs;
- transactional outbox;
- versioned event envelope.

### Этап B — Gateway MVP

- WebSocket Gateway;
- Identify/Ready/Heartbeat/Resume;
- messages, communities, channels, members, roles;
- intents;
- shared session/replay store;
- один shard;
- SDK prototype.

### Этап C — interactions

- command CRUD/sync;
- chat input commands;
- typed options;
- defer/follow-up/ephemeral;
- autocomplete;
- buttons/selects/modals;
- client UI.

### Этап D — OAuth2/installations

- Authorization Code + PKCE;
- scopes;
- community/user installations;
- consent/re-consent/revoke;
- DM interactions;
- team/secret management.

### Этап E — scale and operations

- sharding;
- privileged intents;
- event/webhook delivery log;
- durable replay;
- metrics/dashboard;
- graceful deploy/drain;
- conformance suite.

### Этап F — voice

- bot voice scopes/permissions;
- voice Gateway handshake;
- media credentials;
- transmit/receive;
- reconnect/revoke;
- privacy indicators;
- SDK transport contract.

### Этап G — sunset legacy SSE

- измерить долю Gateway migrations;
- предупредить минимум за 6 месяцев;
- прекратить создание новых legacy integrations;
- оставить read-only migration guide;
- отключать только после достижения критериев ниже.

## 67. Условия отключения legacy SSE

- Gateway работает в production не менее 90 дней;
- error/reconnect metrics находятся в допустимом SLO;
- есть минимум один официальный SDK;
- существует migration guide;
- все официальные примеры переведены;
- разработчики получили уведомление;
- нет известных событий, доступных только через legacy SSE;
- replay/resume проверены при rolling deploy и падении node;
- опубликована окончательная дата sunset.

---

# Часть XII. Тестирование и приёмка

## 68. Обязательные классы тестов

### Unit

- schema validation;
- permissions/intents/scopes;
- idempotency;
- rate-limit buckets;
- signature verification;
- OAuth PKCE;
- event filtering;
- payload redaction.

### Integration

- DB mutation + outbox event atomicity;
- Gateway Identify/Resume;
- reconnect на другой node;
- revoke token закрывает session;
- permission change изменяет последующие payload;
- command registration → client discovery → interaction → response;
- deferred/follow-up/ephemeral lifecycle;
- webhook retries и deduplication;
- file upload/scan/publication;
- voice token grant/revoke.

### Contract

- OpenAPI examples проходят validation;
- AsyncAPI event fixtures проходят validation;
- unknown optional field не ломает official SDK;
- все публичные error codes документированы;
- реестр handlers совпадает со спецификацией.

### Load

- минимум 10 000 одновременных Gateway sessions в целевой среде либо обоснованный
  поэтапный target;
- burst событий без неограниченного роста памяти;
- shard reconnect storm;
- webhook retry backlog;
- общий rate limiter на нескольких nodes;
- interaction ACK p95 ниже 500 мс внутри VoiceRoute до доставки приложению;
- event publish-to-Gateway p95 ниже согласованного SLO.

### Chaos

- restart API node;
- restart event dispatcher;
- временная потеря Redis/broker;
- DB failover;
- duplicate outbox delivery;
- out-of-order worker completion;
- network partition;
- rolling deploy;
- expired resume session.

### Security

- token replay;
- forged interaction signature;
- stale timestamp;
- OAuth redirect mismatch;
- PKCE downgrade;
- scope escalation;
- cross-community IDOR;
- hidden-resource enumeration;
- SSRF через embeds/media;
- malicious upload;
- log secret scan;
- webhook secret rotation race.

## 69. SLO первого production-релиза

Предлагаемые начальные цели:

| Метрика | Цель |
| --- | --- |
| REST availability | 99.9% в месяц |
| Gateway availability | 99.9% в месяц |
| Event delivery p95 | ≤ 1 секунда |
| Resume success при допустимом окне | ≥ 99.9% |
| Interaction internal dispatch p95 | ≤ 500 мс |
| Потерянные committed domain events | 0 |
| Неавторизованная cross-community доставка | 0 |
| Secret в обычных application logs | 0 |

SLO должны быть адаптированы к ресурсам проекта, но обязаны существовать и измеряться.

## 70. Сквозные acceptance scenarios

### Сценарий 1. Установка и команда

1. Разработчик создаёт application.
2. Регистрирует `/ping`.
3. Администратор устанавливает приложение с минимальными permissions.
4. Команда появляется в picker.
5. Пользователь вызывает её.
6. Бот получает interaction один или несколько раз с одинаковым interaction ID.
7. Бот отвечает один раз.
8. Ответ виден пользователю.
9. Uninstall немедленно прекращает новые события.

### Сценарий 2. Reconnect

1. Бот получает последовательность `100`.
2. Gateway node завершается.
3. Бот подключается к другому node.
4. Resume с `100` успешен.
5. Бот получает `101+` без логической потери.
6. Возможные дубликаты имеют тот же event ID.

### Сценарий 3. Изменение permissions

1. Бот имеет `sendMessages`.
2. Администратор отзывает право.
3. Бот получает permission/channel/member update.
4. Следующая отправка возвращает structured `MISSING_PERMISSION`.
5. Старые cached permissions не позволяют обойти сервер.

### Сценарий 4. Privileged intent

1. Непроверенное приложение запрашивает `messageContent` сверх допустимого масштаба.
2. Identify отклоняется стабильным close/error code.
3. После approval Gateway принимает intent.
4. Без intent события сообщений приходят без body.

### Сценарий 5. Voice revoke

1. Бот входит в voice channel.
2. Получает краткоживущий media credential.
3. Администратор удаляет установку.
4. Gateway и media session закрываются.
5. Старый credential не позволяет reconnect.

---

# Часть XIII. Зависимости и рекомендуемая реализация

## 71. Серверные компоненты

Минимально потребуются:

- PostgreSQL для authoritative domain state;
- transactional outbox tables;
- общее ephemeral/session storage, например Redis;
- event dispatcher;
- Gateway service;
- webhook delivery workers;
- scheduled cleanup workers;
- media control adapter к текущему LiveKit;
- metrics/tracing backend.

Конкретный broker не навязывается. Важны свойства: durable delivery, consumer groups,
partition ordering и наблюдаемый backlog.

## 72. Минимальные новые таблицы

Ориентировочно:

```text
application_oauth_clients
application_secrets
application_redirect_uris
application_team_members
application_installations
application_grants
application_commands
application_command_permissions
gateway_sessions
event_outbox
event_replay
event_subscriptions
event_deliveries
interaction_tokens
idempotency_records
developer_audit_log
upload_sessions
```

Названия могут отличаться. Миграции только аддитивные на первом этапе, с rollback plan и
без удаления legacy-данных.

## 73. Индексы и retention

- уникальный индекс application command в пределах type/name/scope;
- уникальный active installation на application + target;
- уникальный idempotency scope + key;
- outbox индекс по unpublished/createdAt;
- replay индекс по shard/sequence;
- delivery индекс по subscription/status/nextAttemptAt;
- TTL cleanup для interaction tokens, sessions, idempotency и replay;
- audit retention задаётся отдельно и не смешивается с техническими delivery logs.

---

# Часть XIV. Что требуется от Python SDK после реализации API

После появления серверных контрактов `voiceroute.py` должен получить:

- `GatewayClient` с Identify/Resume/heartbeat;
- intents enum;
- shard manager;
- полный event model;
- cache/reconciliation policy;
- application command tree;
- interaction context;
- defer/follow-up/ephemeral response API;
- component and modal builders;
- OAuth2 helper;
- webhook signature verification;
- voice adapter;
- distributed cursor/session storage hooks;
- generated или проверяемые OpenAPI models;
- conformance tests.

До появления серверного interaction API prefix-команды остаются отдельной compatibility
функцией и не должны называться настоящими slash commands.

---

# Часть XV. Приоритеты

## 74. P0 — без этого платформа не масштабируется

1. API v1, structured errors, request IDs.
2. Общая идемпотентность.
3. Transactional outbox.
4. Gateway Identify/Heartbeat/Resume.
5. Shared sessions и replay.
6. Полная базовая event model.
7. Intents.
8. Application commands и interaction lifecycle.
9. OAuth2 Authorization Code + PKCE, scopes и installations.
10. Distributed rate limits.
11. Security signatures и secret rotation.
12. OpenAPI/AsyncAPI и contract CI.

## 75. P1 — уровень зрелой bot platform

1. Components/modals/autocomplete.
2. Ephemeral and rich messages.
3. User installations и DM interactions.
4. Sharding.
5. Webhook event subscriptions.
6. Полные member/role/channel/moderation events.
7. Bot presence.
8. Developer teams, audit and analytics.
9. Upload sessions.
10. Sandbox и conformance suite.

## 76. P2 — уровень выше базового Discord parity

1. Durable pull subscriptions и ACK.
2. Manual replay/dead-letter console.
3. Serverless runtime или managed workers.
4. Managed KV/secrets/queues для приложений.
5. Расширенные формы и UI components.
6. AI-oriented streaming interactions и tool schemas.
7. Data residency и enterprise controls.
8. Application catalog and verification.
9. Usage/billing API при необходимости.

## 77. P3 — после стабилизации текстовой платформы

1. Полный сторонний voice transport.
2. Video/screenshare для приложений.
3. Recording/transcription policy.
4. Activities/embedded applications.

Voice handshake можно проектировать параллельно, но его production-выпуск не должен
задерживать Gateway и interactions.

---

# Часть XVI. Definition of Done

Платформа v1 считается готовой к публичной beta, если:

- опубликованы OpenAPI и AsyncAPI;
- Gateway поддерживает reconnect/resume между nodes;
- нет обязательного отдельного SSE на каждый канал;
- есть минимум 20 основных domain events;
- intents реально фильтруют payload;
- slash-команда регистрируется, появляется в UI и вызывает interaction;
- доступны defer, follow-up и ephemeral response;
- buttons/selects/modals проходят сквозной тест;
- OAuth2 PKCE и community/user installations работают;
- revoke закрывает активные sessions;
- rate limits едины для нескольких API instances;
- structured errors и request IDs покрывают все v1 endpoints;
- token/signature security прошла отдельный тест;
- SDK conformance fixtures опубликованы;
- rolling deploy не теряет committed events;
- есть dashboard доставки и ошибок;
- существует migration guide с legacy SSE;
- документация dev и production не противоречит друг другу;
- официальный пример бота не требует `community_id` и `channel_id` для глобального
  получения разрешённых событий;
- production smoke проверяет installation → command → interaction → response → uninstall.

## 78. Итог

Текущий VoiceRoute уже имеет значительную предметную основу: сообщества, роли, каналы,
сообщения, форумы, модерацию, webhooks, stage и media-инфраструктуру. Для выхода на уровень
полноценной платформы ботов основная работа должна быть сосредоточена не на добавлении ещё
нескольких CRUD endpoints, а на четырёх фундаментальных контрактах:

1. **Gateway с resume, intents, sharding и полной моделью событий.**
2. **Application Commands, Interactions и интерактивные сообщения.**
3. **OAuth2, scopes и установки приложений.**
4. **Распределённая эксплуатационная основа: outbox, replay, idempotency, rate limits,
   observability и versioned specifications.**

После них VoiceRoute сможет поддерживать не только простого `ping`-бота, но и большие
модерационные системы, support-ботов, AI-ассистентов, workflow-интеграции и, после выпуска
voice transport, полноценных голосовых приложений.

## 79. Нормативные ориентиры

ТЗ не требует копирования Discord API один в один. Для сверки зрелости контрактов полезны:

- [Discord Application Commands](https://docs.discord.com/developers/docs/interactions/slash-commands);
- [Discord OAuth2](https://discord.com/developers/docs/topics/oauth2);
- [Discord Gateway](https://docs.discord.com/developers/events/gateway);
- [Discord Voice Connections](https://docs.discord.com/developers/topics/voice-connections);
- [OAuth 2.0 Authorization Framework, RFC 6749](https://www.rfc-editor.org/rfc/rfc6749);
- [OAuth 2.0 PKCE, RFC 7636](https://www.rfc-editor.org/rfc/rfc7636);
- [OpenAPI 3.1](https://spec.openapis.org/oas/v3.1.0);
- [AsyncAPI](https://www.asyncapi.com/docs/reference/specification/latest).

При расхождении ориентиров с требованиями безопасности и архитектурой VoiceRoute
приоритет имеет явно версионированный контракт VoiceRoute.
