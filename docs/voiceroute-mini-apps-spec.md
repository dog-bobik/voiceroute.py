# Техническое задание: VoiceRoute Mini Apps для ботов

## 1. Статус документа

Документ описывает универсальную платформенную возможность **VoiceRoute Mini Apps**:
встраиваемые веб-приложения ботов, которые открываются внутри клиента
[VoiceRoute](https://voiceroute.cc), получают безопасный контекст текущего пользователя и
могут работать одновременно с командами, interactions, Gateway и другими способами
управления ботом.

Приложенные к ТЗ изображения являются визуальными референсами:

1. первое изображение показывает рекомендуемый формат окна Mini App поверх текущего
   интерфейса VoiceRoute;
2. второе изображение показывает требуемое расположение кнопки открытия Mini App в
   карточке бота.

Изображения не являются точной спецификацией цветов, размеров или предметной области.
Финальный интерфейс должен использовать дизайн-систему VoiceRoute и корректно работать в
web, desktop и поддерживаемых мобильных клиентах.

## 2. Термины

- **Application** — приложение, зарегистрированное в кабинете разработчика VoiceRoute.
- **Bot** — bot identity приложения, если она создана.
- **Mini App** — веб-интерфейс приложения, открываемый внутри клиента VoiceRoute.
- **Host** — официальный клиент VoiceRoute, содержащий Mini App.
- **Mini App session** — короткоживущая авторизованная сессия конкретного пользователя.
- **Instance** — логический общий экземпляр состояния Mini App. Несколько пользователей
  могут одновременно быть подключены к одной instance.
- **Action** — намерение пользователя изменить состояние или выполнить операцию.
- **State** — канонический снимок общего состояния instance, опубликованный приложением.
- **Launch policy** — условия, при которых пользователь может открыть Mini App.
- **Action policy** — условия, при которых пользователь может выполнить конкретное action.
- **Host Bridge** — безопасный `postMessage`-протокол между Host и Mini App.

## 3. Цель

Разработчик должен иметь возможность добавить к боту полноценный интерактивный
веб-интерфейс. Пользователь открывает карточку бота, нажимает кнопку **«Открыть
приложение»** и получает Mini App поверх текущего интерфейса VoiceRoute.

Mini App и команды не должны быть двумя независимыми системами. Команда, кнопка,
interaction, HTTP-интеграция или действие в Mini App должны обращаться к одной предметной
логике приложения и изменять одно каноническое состояние. Все подключённые пользователи
должны получать согласованные обновления в реальном времени.

Платформа должна решать следующие задачи:

- безопасный запуск стороннего веб-приложения;
- подтверждённая идентичность пользователя и контекст запуска;
- отсутствие передачи Mini App bot token, cookie VoiceRoute и иных долгоживущих секретов;
- синхронизация общего состояния между несколькими пользователями;
- совместная работа Mini App и bot commands;
- декларативные и динамически пересчитываемые ограничения доступа;
- защита от конфликтов, повторов и устаревших изменений;
- нормальная работа после reconnect, смены канала, потери permissions и отзыва установки;
- единый контракт для web, desktop и будущих мобильных клиентов;
- документация и официальный SDK для Mini App.

## 4. Обязательные пользовательские сценарии

### 4.1. Открытие из карточки бота

1. Пользователь открывает карточку бота из списка участников.
2. Если у приложения опубликован и разрешён Mini App, в карточке отображается кнопка
   **«Открыть приложение»**.
3. Кнопка располагается после основного описания бота и до списка полезных команд, как на
   втором приложенном изображении.
4. Host проверяет доступность запуска в текущем контексте.
5. Mini App открывается поверх текущего интерфейса без перехода на внешнюю вкладку.
6. После загрузки Mini App получает контекст, тему, доступные capabilities и текущее
   каноническое состояние.

Если Mini App у приложения отсутствует, кнопка не отображается. Если Mini App существует,
но временно недоступен в текущем контексте, допускается disabled-состояние с понятным
объяснением причины. Нельзя показывать кнопку, которая после нажатия отвечает общей
непонятной ошибкой.

### 4.2. Одновременная работа нескольких пользователей

1. Два пользователя открывают одну logical instance Mini App.
2. Оба получают одну версию состояния.
3. Первый пользователь выполняет разрешённое действие.
4. Бот или backend приложения обрабатывает action и публикует следующую версию state.
5. Оба окна получают одно и то же обновление.
6. Если второй пользователь отправил действие на основании старой версии, приложение
   получает исходную версию и может принять, отклонить либо преобразовать действие.
7. После reconnect клиент получает актуальный snapshot и продолжает поток с cursor.

### 4.3. Совместная работа команд и Mini App

1. Пользователь выполняет команду бота.
2. Обработчик команды вызывает ту же domain service, что и Mini App action.
3. После успешной транзакции приложение публикует новую версию state.
4. Все открытые Mini Apps получают обновление.
5. Обратный сценарий работает аналогично: действие из Mini App меняет состояние, которое
   затем видят команды и следующие interactions.

Нельзя требовать, чтобы разработчик вручную поддерживал два несвязанных состояния — одно
для команд, другое для Mini App.

### 4.4. Динамическое ограничение управления

Платформа должна поддерживать ограничения, зависящие от текущего контекста. Например,
интерфейс управления некоторой совместной активностью может быть доступен для просмотра
всем участникам сообщества, но изменять состояние разрешено только пользователям, которые
находятся в одном voice-канале с ботом. Это только пример политики, а не специальная
музыкальная функциональность.

При выходе пользователя из нужного канала или потере permissions открытое окно должно
немедленно получить обновление capabilities. Недостаточно проверить условие только в
момент открытия Mini App.

## 5. Модель продукта

### 5.1. Mini App как часть Application

Mini App принадлежит `applicationId`, а не отдельному bot user. Это позволяет в будущем
использовать Mini App у приложений с optional bot identity и в разрешённых private
contexts.

В MVP для одного Application достаточно одного опубликованного Mini App manifest. Модель
данных должна допускать несколько entry points в будущем без изменения launch protocol.

### 5.2. Контексты запуска

Поддерживаемые контексты:

- `COMMUNITY` — карточка установленного бота в сообществе;
- `CHANNEL` — запуск с текущим текстовым или голосовым каналом;
- `BOT_DM` — опционально, если приложение установлено пользователем;
- `PRIVATE_CHANNEL` — опционально, если это разрешено installation и manifest;
- `GLOBAL` — только для приложений, которым не требуется community context.

MVP обязан поддерживать `COMMUNITY` и передачу текущего `channelId`. Остальные контексты
можно выпускать поэтапно, но формат manifest и session context не должен их блокировать.

### 5.3. Scope общей instance

Разработчик выбирает способ вычисления instance:

- `APPLICATION` — одно состояние на всё приложение;
- `INSTALLATION` — состояние отдельной установки;
- `COMMUNITY` — одно состояние на сообщество;
- `CHANNEL` — отдельное состояние на канал;
- `VOICE_CHANNEL` — отдельное состояние на voice-канал;
- `USER` — персональное состояние пользователя;
- `CUSTOM` — приложение возвращает валидированный `instanceKey` через серверный callback.

Для каждой сессии VoiceRoute вычисляет непрозрачный `instanceId`. Mini App не должен
самостоятельно собирать security-sensitive instance ID из URL-параметров.

При `VOICE_CHANNEL` необходимо определить поведение отсутствующего voice context:

- запрет запуска;
- запуск read-only instance сообщества;
- запуск персональной instance;
- выбор текущего voice-канала бота.

Выбранная стратегия задаётся manifest и возвращается в launch context.

## 6. Настройка в кабинете разработчика

В настройках Application добавить раздел **Mini App**.

Настраиваемые поля:

```json
{
  "enabled": true,
  "name": "Control Center",
  "description": "Интерактивная панель приложения",
  "launchUrl": "https://app.example.com/voiceroute",
  "allowedOrigins": ["https://app.example.com"],
  "contexts": ["COMMUNITY", "CHANNEL"],
  "instanceScope": "COMMUNITY",
  "openMode": "FLOATING",
  "window": {
    "minWidth": 480,
    "minHeight": 360,
    "preferredWidth": 960,
    "preferredHeight": 720,
    "allowedDisplayModes": ["COMPACT", "NORMAL", "EXPANDED"]
  },
  "requestedCapabilities": [
    "context.read",
    "state.read",
    "actions.create"
  ],
  "launchPolicy": {},
  "actionPolicies": {},
  "version": "7"
}
```

Требования:

- `launchUrl` использует HTTPS, кроме явно разрешённого localhost в development/sandbox;
- redirects при запуске запрещены либо повторно проверяются по allowlist;
- все origins должны быть exact origins без wildcard;
- URL не должен содержать секреты;
- изменение security-sensitive полей требует `If-Match` и `Idempotency-Key`;
- изменения журналируются;
- отключение Mini App немедленно отзывает launch-сессии;
- `minWidth`, `minHeight`, `preferredWidth` и `preferredHeight` являются пожеланиями
  приложения в пределах platform limits, а не разрешением управлять системным окном;
- manifest не может запретить пользователю перемещать, уменьшать, расширять или закрывать
  окно;
- UI показывает статус domain verification, последнюю проверку и диагностическую ошибку;
- secret или bot token никогда не отображается и не передаётся Mini App.

### 6.1. Подтверждение домена

До публикации Mini App разработчик должен подтвердить владение origin одним из способов:

- файл `/.well-known/voiceroute-mini-app.json`;
- DNS TXT challenge;
- существующий подтверждённый application domain VoiceRoute.

Проверка должна защищаться от SSRF, DNS rebinding, redirects на private addresses и
подмены origin. Повторная проверка нужна при изменении `launchUrl` или `allowedOrigins`.

### 6.2. Draft и публикация

Желательно разделить:

- draft manifest;
- проверку manifest;
- preview в sandbox;
- published manifest.

Ошибочная draft-конфигурация не должна ломать уже опубликованный Mini App. Публикация —
атомарная versioned mutation.

## 7. Launch protocol

### 7.1. Создание launch session

Host вызывает:

```http
POST /api/v1/applications/{applicationId}/mini-app/sessions
Content-Type: application/json
Idempotency-Key: UUID
```

```json
{
  "context": {
    "type": "COMMUNITY",
    "communityId": "UUID",
    "channelId": "UUID"
  },
  "client": {
    "platform": "desktop",
    "locale": "ru",
    "theme": "dark"
  },
  "pkceChallenge": "BASE64URL_SHA256"
}
```

Endpoint работает от human session текущего пользователя. Сервер обязан проверить:

- существование опубликованного Mini App;
- действующую installation;
- членство и видимость контекста;
- manifest contexts;
- launch policy;
- отсутствие block/revoke;
- текущую версию manifest;
- лимиты запуска.

Ответ:

```json
{
  "sessionId": "UUID",
  "instanceId": "UUID",
  "launchUrl": "https://app.example.com/voiceroute",
  "launchCode": "ONE_TIME_OPAQUE_CODE",
  "expiresAt": "2026-10-26T13:00:30.000Z",
  "targetOrigin": "https://app.example.com",
  "bridgeVersion": 1
}
```

`launchCode`:

- одноразовый;
- живёт не более 60 секунд;
- привязан к session, user, application, exact origin и PKCE challenge;
- не является OAuth token;
- не даёт доступ к bot API;
- не должен попадать в query string, Referer, логи или analytics URL.

### 7.2. Инициализация Host Bridge

1. Host создаёт sandboxed iframe/webview с `launchUrl` без credentials.
2. Mini App отправляет `VR_MINI_APP_READY` через `postMessage`.
3. Host проверяет `event.origin` и `event.source`.
4. Host отвечает `VR_MINI_APP_INIT`, передавая launch code, bridge version, theme и
   viewport.
5. Mini App обменивает code на session access token.

Нельзя передавать launch code до получения `READY` от exact configured origin.

### 7.3. Обмен launch code

```http
POST /api/v1/mini-app/sessions/exchange
Origin: https://app.example.com
```

```json
{
  "launchCode": "ONE_TIME_OPAQUE_CODE",
  "pkceVerifier": "RANDOM_VERIFIER"
}
```

Ответ:

```json
{
  "accessToken": "SHORT_LIVED_MINI_APP_TOKEN",
  "tokenType": "MiniApp",
  "expiresIn": 900,
  "session": {
    "id": "UUID",
    "applicationId": "UUID",
    "instanceId": "UUID"
  }
}
```

Токен живёт не более 15 минут и может продлеваться только через Host Bridge при всё ещё
действующей human session. Mini App не получает refresh token длительного хранения.

### 7.4. Получение контекста

```http
GET /api/v1/mini-app/@me
Authorization: MiniApp <token>
```

Пример ответа:

```json
{
  "sessionId": "UUID",
  "application": {"id": "UUID", "name": "Example"},
  "user": {"id": "42", "username": "user", "displayName": "User"},
  "installationId": "UUID",
  "instanceId": "UUID",
  "context": {
    "type": "COMMUNITY",
    "communityId": "UUID",
    "channelId": "UUID",
    "voiceChannelId": null
  },
  "capabilities": {
    "state.read": {"allowed": true},
    "actions.create": {"allowed": false, "reasonCode": "VOICE_CONTEXT_REQUIRED"}
  },
  "locale": "ru",
  "theme": "dark",
  "expiresAt": "..."
}
```

Данные контекста предназначены для UI. Они не заменяют серверную авторизацию каждого
action.

## 8. Авторизация и политики

### 8.1. Разделение прав

Проверки разделяются минимум на три уровня:

- `OPEN` — можно открыть Mini App;
- `READ_STATE` — можно читать state instance;
- `ACTION` — можно выполнить определённое действие.

Разработчик может разрешить открытие и чтение, но запретить изменение. UI должен получать
machine-readable reason и переходить в read-only режим.

### 8.2. Допустимые условия policy

Декларативная policy должна поддерживать:

- действующую installation;
- тип installation: `COMMUNITY` или `USER`;
- membership пользователя;
- разрешённые contexts;
- список обязательных community permissions;
- `rolesAny`, `rolesAll`;
- allow/deny для отдельных communities/channels;
- current channel visibility;
- отсутствие timeout/ban;
- `USER_IN_VOICE`;
- `APPLICATION_IN_VOICE`;
- `SAME_VOICE_CHANNEL_AS_APPLICATION`;
- конкретный тип канала;
- owner/administrator/moderator requirement;
- пользовательский consent scope;
- возраст/verification приложения, если появятся такие платформенные признаки.

Нельзя добавлять произвольный исполняемый код разработчика внутрь policy engine.

### 8.3. Policies отдельных actions

Manifest может описывать action names и требования:

```json
{
  "actionPolicies": {
    "item.add": {
      "permissionsAll": ["viewChannel"],
      "voice": "SAME_VOICE_CHANNEL_AS_APPLICATION"
    },
    "settings.update": {
      "permissionsAll": ["manageCommunity"]
    }
  }
}
```

Названия actions определяет приложение. VoiceRoute проверяет формат, лимиты и policy, но
не интерпретирует предметный смысл `item.add` или `settings.update`.

### 8.4. Обязательная повторная проверка

Policy проверяется:

1. при создании launch session;
2. при exchange;
3. при чтении state;
4. при каждом action;
5. перед доставкой action приложению;
6. перед публикацией чувствительных обновлений;
7. периодически для активной session;
8. при событиях membership, permissions, roles, voice state, installation revoke и ban.

Это защищает от TOCTOU: пользователь не сохраняет право управления только потому, что
открыл окно раньше.

### 8.5. Изменение capabilities в реальном времени

При изменении условий Host/Mini App получает:

```json
{
  "type": "CAPABILITIES_UPDATED",
  "sequence": "91",
  "capabilities": {
    "state.read": {"allowed": true},
    "actions.create": {"allowed": false, "reasonCode": "VOICE_CONTEXT_LOST"}
  }
}
```

UI обязан немедленно отключить соответствующие controls. Сервер всё равно повторно
проверяет action и не доверяет UI.

## 9. Синхронизация общего состояния

### 9.1. Основной принцип

VoiceRoute не должен считать локальный React/Vue state каноническим. Каноническое
состояние принадлежит backend приложения либо опциональному platform state store.

Рекомендуемый поток:

```text
Mini App -> Action -> VoiceRoute -> Bot/backend -> domain transaction
         -> State publish -> VoiceRoute realtime -> все Mini App sessions
```

Команды используют ту же domain transaction и тот же State publish.

### 9.2. Platform-managed state

Для простых и средних приложений предоставить ограниченное versioned JSON-хранилище.

```http
GET /api/v1/mini-app/instances/{instanceId}/state
Authorization: MiniApp <token>
```

```json
{
  "instanceId": "UUID",
  "version": "9007199254740997",
  "updatedAt": "...",
  "updatedBy": {"type": "APPLICATION", "id": "UUID"},
  "state": {}
}
```

Публикация state доступна bot credential, OAuth client credential с отдельным scope либо
доверенному application callback:

```http
PUT /api/v1/applications/{applicationId}/mini-app/instances/{instanceId}/state
Authorization: Bot <token>
If-Match: "state-9007199254740997"
Idempotency-Key: UUID
```

```json
{
  "state": {},
  "causedByActionId": "UUID"
}
```

Требования:

- version — десятичная строка;
- compare-and-set через `If-Match`;
- mutation и outbox event атомарны;
- повтор того же idempotency key возвращает исходный результат;
- state не содержит секретов, токенов, бинарных файлов и персональных данных без
  обоснованной необходимости;
- рекомендуемый предел snapshot — 64 KiB, абсолютный — 256 KiB;
- ограничение частоты публикаций на application и instance;
- сервер хранит последнюю версию и bounded журнал изменений для reconnect;
- приложение может отключить platform-managed state и использовать собственный backend.

### 9.3. Actions вместо прямой записи UI

Mini App не должен напрямую перезаписывать shared state. Он отправляет action:

```http
POST /api/v1/mini-app/instances/{instanceId}/actions
Authorization: MiniApp <token>
Idempotency-Key: UUID
```

```json
{
  "name": "item.add",
  "expectedStateVersion": "9007199254740997",
  "payload": {"itemId": "example"},
  "clientActionId": "UUID"
}
```

Ответ:

```json
{
  "actionId": "UUID",
  "status": "PENDING",
  "acceptedAt": "..."
}
```

Action доставляется приложению через существующие механизмы Bot Platform:

- Gateway;
- durable pull subscription;
- подписанный HTTPS callback.

Приложение отвечает одним из статусов:

- `ACKNOWLEDGED`;
- `COMPLETED`;
- `REJECTED`;
- `FAILED`;
- `EXPIRED`.

Для `REJECTED` возвращается безопасный machine-readable code и локализуемое сообщение.

### 9.4. Realtime transport Mini App

Нужен отдельный клиентский realtime-канал, привязанный к Mini App session. Допустимы:

- WebSocket `/api/v1/mini-app/socket`;
- Host Bridge, если Host мультиплексирует соединение;
- SSE как fallback.

Канал передаёт только разрешённые session-specific данные:

- `STATE_SNAPSHOT`;
- `STATE_UPDATED`;
- `ACTION_STATUS_UPDATED`;
- `CAPABILITIES_UPDATED`;
- `CONTEXT_UPDATED`;
- `SESSION_REVOKED`;
- `RECONNECT_REQUIRED`.

Требования:

- sequence хранится строкой;
- reconnect/resume с последнего подтверждённого sequence;
- повторная доставка допустима;
- после потери replay window выполняется snapshot reconciliation;
- события другой instance не передаются;
- изменение visibility или policy прекращает дальнейшую доставку;
- session token не даёт подписаться на произвольный `instanceId`.

### 9.5. Конфликты и порядок

- Порядок гарантируется внутри одной instance.
- Глобальный порядок между разными instance не требуется.
- Все actions имеют `actionId`, `clientActionId`, actor и observed state version.
- Сервер не выполняет blind last-write-wins для shared state.
- Приложение может принять action со старой версией, если предметная операция коммутативна.
- При конфликте state publish возвращается `409 STATE_VERSION_CONFLICT` и current ETag.
- UI может использовать optimistic update, но обязан откатить его после reject/conflict.
- Для времени и прогресса используется server timestamp, а не локальный таймер как источник
  истины.

### 9.6. Присутствие Mini App

Опционально приложение может получать агрегированное количество активных viewers instance,
но не полный список пользователей без отдельной необходимости и разрешения. Presence Mini
App не должна автоматически становиться публичным пользовательским presence VoiceRoute.

## 10. Связь с commands и interactions

### 10.1. Единая domain logic

Документация и SDK должны рекомендовать структуру:

```text
Command handler ----\
Component handler ---+--> Application service --> Repository/transaction
Mini App action -----/             |
                                   +--> publish Mini App state
```

Нельзя рекомендовать обработчикам команд изменять только сообщение, а Mini App actions —
только browser state.

### 10.2. Открытие Mini App из команды или component

Добавить interaction response/component типа `OPEN_MINI_APP`:

```json
{
  "type": "OPEN_MINI_APP",
  "context": {"type": "COMMUNITY", "communityId": "UUID"},
  "entryPoint": "default"
}
```

Host всё равно создаёт новую launch session и проверяет policy. Interaction не может
передать готовый access token.

### 10.3. Вызов команды из Mini App

Не следует эмулировать отправку текстового сообщения `/command`. Если разработчику нужна
общая операция, Mini App отправляет action, а command и action используют общий service.

В будущем Host Bridge может предоставлять `invokeCommand`, но оно должно создавать
настоящее application interaction с проверками command permissions, а не внедрять текст в
чат.

### 10.4. Функциональность Mini App и команд не обязана совпадать

Набор возможностей Mini App не обязан совпадать с набором application commands. Mini App
может предоставлять дополнительные экраны, действия, визуальные редакторы, массовые
операции, аналитику и многошаговые процессы, для которых команда отсутствует.

Допустимы все варианты:

- операция существует только в Mini App;
- операция существует только как command;
- операция доступна обоими способами;
- Mini App и command используют разные access policies;
- Mini App предоставляет расширенную версию простого командного сценария.

Требование общей domain logic применяется только к операциям с одинаковым предметным
смыслом. Для них command и Mini App не должны реализовывать конфликтующие правила или
изменять разные копии состояния. Нельзя требовать добавления отдельной команды для каждой
функции Mini App.

## 11. UI и UX Host

### 11.1. Кнопка в карточке бота

Кнопка **«Открыть приложение»**:

- находится в карточке бота после описания и до полезных команд;
- занимает доступную ширину основного контента карточки;
- содержит иконку external/app launch, но не выглядит как внешняя ссылка;
- имеет loading state без изменения геометрии карточки;
- доступна с клавиатуры;
- имеет понятный accessible name;
- не отображается у приложений без опубликованного Mini App;
- отображает причину недоступности без раскрытия приватных permissions или существования
  скрытых ресурсов.

### 11.2. Контейнер Mini App

Окно открывается поверх текущего интерфейса, как на первом референсе.

Требования desktop/web:

- перемещаемое floating modal/overlay, не новая вкладка и не отдельное системное окно;
- затемнение фона;
- сохранение текущего community/channel под окном;
- системный header VoiceRoute с названием приложения и кнопками управления окном;
- пользователь может перетаскивать окно за системный header;
- пользователь может изменять ширину и высоту за края и углы окна;
- доступны режимы `COMPACT`, `NORMAL` и `EXPANDED`;
- двойной клик по header переключает `NORMAL`/`EXPANDED`;
- кнопка expand/restore доступна рядом с close;
- `COMPACT` уменьшает окно внутри VoiceRoute, но не сворачивает его в системный dock и не
  приостанавливает realtime-синхронизацию;
- `EXPANDED` занимает максимально допустимую рабочую область VoiceRoute, не перекрывая
  обязательные системные controls;
- минимальные и предпочтительные размеры берутся из manifest, но ограничиваются Host;
- рекомендуемый normal-размер — около 960×720 px;
- окно нельзя уменьшить ниже platform minimum, при котором остаются доступны системный
  header, close и restore;
- окно нельзя переместить полностью или частично за допустимые границы viewport;
- после изменения размера viewport, масштаба, monitor layout или safe area Host возвращает
  окно в видимую область;
- drag и resize используют pointer capture и не передаются содержимому iframe;
- перемещение, resize и смена display mode не перезагружают iframe, не создают новую Mini
  App session и не сбрасывают локальное или общее состояние;
- Host сохраняет последнюю безопасную геометрию локально для пары
  `user + application + client device` и восстанавливает её при следующем запуске;
- геометрия окна не является shared state и не синхронизируется между пользователями;
- пользователь может сбросить сохранённую геометрию к значениям manifest;
- перемещение и изменение размера доступны с клавиатуры и assistive technologies;
- при keyboard move/resize Host объявляет новое положение/размер через accessible live
  region без передачи координат другим пользователям;
- Mini App не может произвольно задавать экранные координаты, удерживать окно поверх всех
  окон ОС, блокировать перемещение или скрывать системные controls;
- Mini App может только запросить предпочтительный display mode, окончательное решение
  принимает Host с учётом пользователя, viewport и accessibility;
- фокус остаётся внутри modal;
- `Escape` закрывает окно, если приложение не сообщает о несохранённых данных;
- подтверждение закрытия поддерживается через ограниченный bridge API;
- при ошибке iframe показывается Host-owned error screen с retry;
- при revoke окно закрывается либо переводится в безопасное состояние;
- приложение не может скрыть системную кнопку закрытия;
- Host показывает origin/имя приложения в security-sensitive сценариях.

Требования mobile:

- full-screen sheet/page;
- свободное перемещение и ручной resize на mobile не требуются;
- `COMPACT` на mobile может отображаться как Host-owned collapsed sheet, если это не
  нарушает доступность; системная кнопка возврата в full-screen обязательна;
- safe-area insets;
- корректная виртуальная клавиатура;
- back gesture сначала передаётся навигации Mini App, затем закрывает контейнер;
- отсутствие горизонтального scroll всего Host.

### 11.3. Theme и viewport

Host передаёт:

- `colorScheme`;
- design tokens только общего назначения;
- `viewport.width/height`;
- текущий `displayMode`;
- текущую Host-owned геометрию content viewport без координат других окон;
- `safeAreaInsets`;
- locale;
- reduced motion;
- contrast preference;
- text scale, если поддерживается клиентом.

Mini App не обязано копировать UI VoiceRoute, но должно корректно поддерживать светлую и
тёмную тему.

### 11.4. Loading lifecycle

Состояния контейнера:

1. `AUTHORIZING`;
2. `LOADING`;
3. `READY`;
4. `DEGRADED`;
5. `RECONNECTING`;
6. `REVOKED`;
7. `FAILED`.

Mini App вызывает `ready()` только после готовности первого полезного кадра. До этого Host
показывает skeleton/spinner с ограниченным timeout.

## 12. Host Bridge API

Опубликовать versioned JavaScript SDK, например `@voiceroute/mini-app-sdk`.

Минимальный интерфейс:

```ts
interface VoiceRouteMiniApp {
  ready(): Promise<void>;
  getContext(): MiniAppContext;
  getCapabilities(): CapabilityMap;
  getTheme(): ThemeParams;
  getViewport(): Viewport;
  getDisplayMode(): "COMPACT" | "NORMAL" | "EXPANDED";
  requestClose(options?: { confirmUnsaved?: boolean }): Promise<void>;
  expand(): Promise<void>;
  restore(): Promise<void>;
  requestDisplayMode(mode: "COMPACT" | "NORMAL" | "EXPANDED"): Promise<void>;
  openExternal(url: string): Promise<void>;
  subscribe(event: MiniAppHostEvent, handler: Handler): Unsubscribe;
  createAction(name: string, payload: unknown, options?: ActionOptions): Promise<Action>;
  getState(): Promise<MiniAppState>;
}
```

Bridge protocol:

- содержит `bridgeVersion` и unique request IDs;
- проверяет exact origin в обе стороны;
- валидирует schema каждого сообщения;
- ограничивает размер payload;
- имеет timeout и cancellation;
- игнорирует неизвестные optional fields;
- неизвестный обязательный protocol version отклоняется;
- не позволяет Mini App произвольно обращаться к Host DOM;
- не содержит универсального `eval`, filesystem или raw IPC.

Host публикует события `viewportChanged` и `displayModeChanged` после завершения resize,
move между monitor work areas или смены режима. Во время активного resize допускаются
throttled `viewportChanged` не чаще 30 раз в секунду. Mini App не получает и не задаёт
абсолютные координаты окна: они принадлежат Host и не нужны для адаптивной вёрстки.

## 13. Безопасность web/desktop

### 13.1. Изоляция

Для браузера использовать sandboxed iframe. Для Electron/desktop:

- `sandbox: true`;
- `contextIsolation: true`;
- `nodeIntegration: false`;
- отдельный session partition;
- запрет доступа к Electron/Node APIs;
- запрет произвольной навигации;
- проверяемый preload только для Host Bridge;
- запрет создания новых окон без участия Host;
- permission requests deny-by-default;
- camera/microphone/geolocation требуют отдельного будущего capability и явного consent;
- download обрабатывается Host, а не скрыто сохраняется на диск.

### 13.2. CSP и навигация

- Host разрешает frame только для verified origin.
- Mini App обязано разрешить embedding официальными origins VoiceRoute через CSP
  `frame-ancestors`.
- `window.top` navigation блокируется.
- внешние ссылки открываются через `openExternal` с проверкой протокола и подтверждением.
- запрещены `file:`, `javascript:`, custom schemes и loopback в production.
- redirect chain проверяется полностью.
- OAuth внутри Mini App использует отдельное окно/flow Host и exact redirect URI.

### 13.3. Cookies и хранилище

- VoiceRoute cookies не доступны Mini App.
- Mini App не должна зависеть только от third-party cookies.
- Mini App token рекомендуется хранить только в памяти.
- localStorage/IndexedDB разделены по origin и не являются источником shared state.
- logout/revoke очищает Host-owned session material.
- clipboard доступен только через явный bridge action пользователя.

### 13.4. Серверная безопасность

- все security-sensitive mutations используют idempotency;
- access token хранится только в хешированном или криптографически защищённом виде;
- session и action queries всегда ограничены `applicationId` и `instanceId`;
- нельзя перечислять чужие instance/session;
- audit не хранит полный чувствительный state;
- логи не содержат launch code, access token, payload secrets и URL fragments;
- action payload проходит size/depth/schema limits;
- JSON parsing использует общие capacity limits Bot Platform;
- rate limits общие между API nodes и хранятся в PostgreSQL/Redis;
- revoke распространяется на все nodes через общую authoritative state.

## 14. Приватность

Manifest должен содержать:

- privacy URL;
- terms URL;
- deletion URL;
- перечень запрашиваемых user/context fields;
- срок хранения данных Mini App;
- использует ли приложение внешний backend;
- обоснование privileged capabilities.

Пользователь должен понимать, какому приложению передаются данные. Mini App получает только
минимально необходимое:

- user ID, display name и username — если нужны и разрешены;
- текущий context;
- instance ID;
- разрешённые capabilities.

Email, IP, cookie, MFA state, session hash, список друзей и другие данные аккаунта не
передаются.

При удалении пользовательских данных существующий механизм
`APPLICATION_USER_DATA_DELETION_REQUESTED` должен распространяться и на Mini App state,
sessions и application backend callbacks.

## 15. REST API

### 15.1. Developer configuration

```text
GET    /api/v1/developers/applications/{applicationId}/mini-app
PATCH  /api/v1/developers/applications/{applicationId}/mini-app
POST   /api/v1/developers/applications/{applicationId}/mini-app/verify-origin
POST   /api/v1/developers/applications/{applicationId}/mini-app/publish
GET    /api/v1/developers/applications/{applicationId}/mini-app/diagnostics
```

### 15.2. Host/session

```text
POST   /api/v1/applications/{applicationId}/mini-app/sessions
POST   /api/v1/mini-app/sessions/exchange
POST   /api/v1/mini-app/sessions/{sessionId}/renew
DELETE /api/v1/mini-app/sessions/{sessionId}
GET    /api/v1/mini-app/@me
```

### 15.3. State/actions

```text
GET    /api/v1/mini-app/instances/{instanceId}/state
POST   /api/v1/mini-app/instances/{instanceId}/actions
GET    /api/v1/mini-app/actions/{actionId}

GET    /api/v1/applications/{applicationId}/mini-app/instances/{instanceId}/state
PUT    /api/v1/applications/{applicationId}/mini-app/instances/{instanceId}/state
POST   /api/v1/applications/{applicationId}/mini-app/actions/{actionId}/ack
POST   /api/v1/applications/{applicationId}/mini-app/actions/{actionId}/complete
POST   /api/v1/applications/{applicationId}/mini-app/actions/{actionId}/reject
```

Названия маршрутов можно адаптировать к существующим соглашениям Bot Platform, но
обязательное разделение human Host, MiniApp credential и Application/Bot credential должно
сохраниться.

## 16. События Bot Platform

Добавить события:

- `MINI_APP_SESSION_OPENED`;
- `MINI_APP_SESSION_CLOSED`;
- `MINI_APP_ACTION_CREATED`;
- `MINI_APP_ACTION_CANCELLED`;
- `MINI_APP_STATE_UPDATED`;
- `MINI_APP_POLICY_UPDATED`;
- `MINI_APP_ACCESS_REVOKED`.

Для bot/backend в большинстве случаев достаточно `MINI_APP_ACTION_CREATED`. Session
open/close должны быть opt-in и не использоваться для скрытого слежения за пользователем.

Добавить intent `miniApps`:

- не privileged для действий, которые пользователь сам явно отправил приложению;
- session analytics и расширенная viewer identity могут требовать отдельного scope/review;
- state update доставляется только самому application и не публикуется чужим ботам.

Пример action event:

```json
{
  "event": "MINI_APP_ACTION_CREATED",
  "sequence": "9007199254741001",
  "deliveryId": "UUID",
  "schemaVersion": 1,
  "data": {
    "actionId": "UUID",
    "applicationId": "UUID",
    "instanceId": "UUID",
    "name": "item.add",
    "actor": {"id": "42"},
    "context": {
      "type": "COMMUNITY",
      "communityId": "UUID",
      "channelId": "UUID"
    },
    "expectedStateVersion": "19",
    "payload": {"itemId": "example"}
  }
}
```

Доставка должна использовать существующий transactional outbox, current ACL, replay,
durable subscription и HTTPS signature infrastructure.

## 17. Коды ошибок

Добавить структурированные error codes:

- `MINI_APP_NOT_CONFIGURED`;
- `MINI_APP_DISABLED`;
- `MINI_APP_ORIGIN_NOT_VERIFIED`;
- `MINI_APP_CONTEXT_NOT_ALLOWED`;
- `MINI_APP_LAUNCH_FORBIDDEN`;
- `MINI_APP_ACTION_FORBIDDEN`;
- `MINI_APP_SESSION_EXPIRED`;
- `MINI_APP_SESSION_REVOKED`;
- `MINI_APP_LAUNCH_CODE_INVALID`;
- `MINI_APP_LAUNCH_CODE_USED`;
- `MINI_APP_ORIGIN_MISMATCH`;
- `MINI_APP_INSTANCE_NOT_FOUND`;
- `MINI_APP_STATE_VERSION_CONFLICT`;
- `MINI_APP_ACTION_EXPIRED`;
- `MINI_APP_ACTION_ALREADY_RESOLVED`;
- `MINI_APP_PAYLOAD_TOO_LARGE`;
- `MINI_APP_RATE_LIMITED`;
- `MINI_APP_UNAVAILABLE`;
- `MINI_APP_BRIDGE_VERSION_UNSUPPORTED`.

Ошибки используют общий v1 envelope с `requestId`, `retryable`, `details` и
`fieldErrors`. UI ориентируется на code, а не на текст.

## 18. Лимиты

Начальные рекомендуемые ограничения:

- 10 активных Mini App sessions на пользователя;
- 5 активных окон одного Application на пользователя;
- 1000 активных sessions на Application до отдельного повышения;
- launch code TTL: 60 секунд;
- Mini App access token TTL: 15 минут;
- неактивная session: 30 минут;
- максимальная непрерывная session: 8 часов;
- state snapshot: рекомендуемо 64 KiB, максимум 256 KiB;
- action payload: максимум 32 KiB;
- 60 actions в минуту на user/application;
- burst не более 10 actions за 5 секунд;
- 120 state publications в минуту на instance;
- максимум 100 неподтверждённых actions на instance;
- action TTL: 5 минут, настраиваемый в меньшую сторону;
- replay Mini App realtime: минимум 15 минут;
- history action statuses: минимум 24 часа.

Конкретные значения публикуются в `/api/v1/capabilities` и rate-limit headers.

## 19. Capabilities discovery

Расширить `/api/v1/capabilities`:

```json
{
  "features": {
    "miniApps": true,
    "miniAppSharedState": true,
    "miniAppActions": true,
    "miniAppCustomInstances": false
  },
  "miniApps": {
    "bridgeVersions": [1],
    "contexts": ["COMMUNITY", "CHANNEL"],
    "instanceScopes": ["INSTALLATION", "COMMUNITY", "CHANNEL", "VOICE_CHANNEL", "USER"],
    "maxStateBytes": 262144,
    "maxActionBytes": 32768,
    "sessionTtlSeconds": 900
  }
}
```

Клиент не должен определять доступность по номеру версии или наличию UI. Источник истины —
runtime capabilities конкретного deployment.

## 20. Наблюдаемость и эксплуатация

Метрики без high-cardinality labels:

- launch attempts/success/failure;
- active sessions;
- session exchange latency;
- iframe ready latency;
- action accepted/completed/rejected/expired;
- action processing latency;
- state publish conflicts;
- realtime reconnect/resume/fallback;
- policy revocations;
- origin/CSP violations;
- per-application aggregated rate limiting;
- outbox/delivery backlog Mini App events.

В кабинете разработчика показать:

- статус manifest и origin verification;
- активные sessions агрегированно;
- последнюю успешную загрузку;
- error rate;
- median/p95 ready latency;
- action backlog;
- последнюю опубликованную state version по диагностической instance без показа state;
- причины наиболее частых отказов policy;
- инциденты платформы.

Audit log должен фиксировать:

- изменение manifest;
- публикацию/откат версии;
- изменение policies;
- подтверждение origin;
- административный revoke sessions.

Не нужно записывать каждое пользовательское action в community audit log. Для них нужен
отдельный bounded application diagnostic log без чувствительных payload.

## 21. OpenAPI, AsyncAPI и fixtures

Обязательно обновить:

- OpenAPI 3.1;
- AsyncAPI 3.0;
- `/api/v1/capabilities`;
- error-code registry;
- compatibility baseline;
- protocol fixtures Host Bridge;
- event fixtures Mini App;
- conformance fixtures launch/exchange/actions/state;
- signature fixtures для HTTPS delivery;
- официальный Node SDK;
- документацию для авторов сторонних SDK.

Fixtures должны включать sequence/version выше `2^53`, неизвестные optional fields,
повторную доставку, expired/revoked session и conflict.

## 22. SDK

### 22.1. Browser SDK Mini App

Опубликовать package с:

- Host Bridge handshake;
- origin validation;
- context/theme/viewport;
- session exchange;
- state subscription;
- action helper;
- reconnect/resume;
- AbortSignal;
- typed errors;
- feature detection;
- development mock Host.

### 22.2. Bot SDK contract

Официальный Node SDK должен получить:

- типы Mini App events;
- `miniApps.publishState()`;
- `miniApps.getState()`;
- `miniApps.acknowledgeAction()`;
- `miniApps.completeAction()`;
- `miniApps.rejectAction()`;
- helpers для idempotency и state conflicts.

Python и другие сторонние SDK должны иметь достаточно machine-readable контрактов, чтобы
не копировать внутреннюю реализацию сервера.

## 23. Тестирование

### 23.1. Unit tests

- manifest validation;
- exact origin matching;
- PKCE;
- одноразовый launch code;
- policy conditions;
- action schema и limits;
- state compare-and-set;
- idempotency replay;
- bridge request correlation;
- cursor/resume;
- sanitization diagnostic logs.

### 23.2. Интеграционные тесты

- launch от реальной human session;
- запуск только для установленного приложения;
- два пользователя получают одну instance и одинаковый snapshot;
- команда и Mini App action изменяют один state;
- конкурентные actions;
- state conflict;
- rollback domain transaction не публикует state/event;
- commit публикует событие ровно один раз логически;
- reconnect с replay;
- потеря replay window и reconciliation;
- отзыв installation закрывает sessions;
- потеря роли/permission меняет capabilities;
- переход пользователя между voice-каналами меняет action access;
- изменение voice context между check и commit отклоняет action;
- token rotation не раскрывает bot token Mini App;
- другой Application не читает instance;
- другой пользователь не переиспользует launch code;
- wrong Origin и redirect блокируются;
- rate limits общие между API nodes.

### 23.3. Browser/Electron E2E

- кнопка находится в карточке бота в требуемом месте;
- keyboard navigation и focus trap;
- drag окна за системный header мышью и touchpad;
- resize за каждый край и угол без перезагрузки iframe;
- keyboard move/resize и screen-reader announcements;
- переключение `COMPACT`, `NORMAL`, `EXPANDED` и restore;
- двойной клик по header для expand/restore;
- сохранение безопасной геометрии после закрытия и повторного запуска;
- сброс сохранённой геометрии;
- возврат окна в видимую область после уменьшения viewport или отключения монитора;
- запрет выхода за work area и уменьшения ниже minimum;
- сохранение session, shared state и realtime connection при move/resize;
- приложение не может скрыть Host header/close или самостоятельно задать координаты;
- dark/light themes;
- narrow viewport и full-screen mobile;
- загрузка, retry, offline и reconnect;
- два независимых окна синхронизируются;
- read-only controls при запрете actions;
- capabilities меняются без перезагрузки;
- close confirmation;
- external navigation проходит только через Host;
- Node integration отсутствует;
- filesystem/clipboard/media permission закрыты по умолчанию;
- CSP/origin violation показывает безопасную ошибку;
- нет page errors и accessibility violations.

### 23.4. Нагрузочные тесты

- много sessions одной instance;
- fan-out state update;
- burst actions;
- slow consumers;
- reconnect storm;
- restart одного API node;
- lease takeover другим worker;
- backlog и dead-letter callbacks;
- bounded memory;
- отсутствие high-cardinality metrics.

## 24. Критерии приёмки MVP

MVP считается готовым, если одновременно выполнены условия:

1. Разработчик может настроить, проверить и опубликовать Mini App.
2. Кнопка отображается в карточке бота в требуемом месте.
3. Mini App открывается внутри VoiceRoute в sandboxed контейнере.
4. На desktop/web пользователь может перемещать окно и вручную изменять его размер в
   пределах рабочей области VoiceRoute.
5. Режимы `COMPACT`, `NORMAL`, `EXPANDED` и restore работают без перезагрузки Mini App,
   потери session или state.
6. Безопасная геометрия сохраняется локально и корректируется при изменении viewport или
   monitor layout.
7. Mini App не может скрыть Host controls, выйти за work area или самостоятельно назначить
   абсолютные координаты.
8. Mini App не получает bot token, cookie или долгоживущий user token.
9. Launch использует one-time code, exact origin и PKCE.
10. `COMMUNITY` context работает в web и desktop.
11. Два пользователя одной instance получают единый state.
12. Action доставляется приложению через минимум Gateway и один durable transport.
13. Изменение state после команды видно открытым Mini Apps.
14. Изменение state после Mini App action видно всем sessions.
15. Версии, idempotency и conflicts работают при параллельных действиях.
16. `OPEN`, `READ_STATE` и `ACTION` policies разделены.
17. Условия membership, permissions, roles и voice relation повторно проверяются.
18. Потеря доступа обновляет UI и блокирует mutation на сервере.
19. Reconnect/resume и snapshot reconciliation проверены.
20. OpenAPI, AsyncAPI, capabilities, errors и fixtures обновлены.
21. Есть Browser SDK и пример универсального Mini App.
22. Есть contract/integration/browser/Electron tests.
23. Есть метрики, diagnostics и operational alerts.
24. Legacy bots без Mini App продолжают работать без изменений.

## 25. Этапы реализации

### Этап A — manifest и безопасный контейнер

- модель manifest;
- developer UI;
- origin verification;
- кнопка в карточке;
- movable/resizable floating Host container и mobile full-screen;
- режимы compact/normal/expanded, restore и сохранение безопасной геометрии;
- iframe/webview sandbox;
- Host Bridge handshake;
- launch session и exchange.

### Этап B — context и policies

- Mini App credential;
- context endpoint;
- launch/read/action policy engine;
- roles/permissions/membership;
- voice-aware conditions;
- realtime capabilities updates;
- revoke.

### Этап C — actions и shared state

- instance scopes;
- state store;
- action lifecycle;
- Gateway/durable delivery;
- state broadcast;
- conflicts/idempotency;
- reconnect/reconciliation.

### Этап D — SDK и команды

- Browser SDK;
- Node bot SDK;
- typed events;
- `OPEN_MINI_APP` interaction;
- reference architecture для общей domain logic;
- универсальный example app.

### Этап E — эксплуатация

- diagnostics;
- metrics/alerts;
- sandbox preview;
- load/restart/rolling tests;
- security review;
- production feature flag;
- staged rollout.

### Этап F — дополнительные контексты

- BOT_DM;
- PRIVATE_CHANNEL;
- user-installed applications;
- custom instance resolver;
- несколько entry points;
- отдельные capabilities для media/clipboard/files при необходимости.

## 26. Обратная совместимость

- Mini Apps являются opt-in.
- Приложение без manifest работает как раньше.
- Legacy REST/SSE не меняются из-за добавления UI.
- Существующие bot commands и interactions продолжают работать.
- Наличие Mini App не выдаёт дополнительные permissions автоматически.
- Installation и intents не расширяются молча.
- Новый intent/capability не должен считаться выданным существующим приложениям.
- Feature включается через runtime capability и staged rollout.
- Отключение feature не должно ломать команды бота.

## 27. Не входит в MVP

- выполнение backend-кода приложения внутри инфраструктуры VoiceRoute;
- произвольный доступ Mini App к filesystem, Node.js или Host DOM;
- автоматическое доверие внешнему origin без verification;
- передача bot token браузеру;
- универсальная синхронизация произвольной базы данных разработчика;
- offline-first редактирование сложных документов;
- платежи и биллинг;
- встроенный магазин Mini Apps;
- camera/microphone/geolocation без отдельного будущего контракта;
- несколько Mini Apps одного Application, если это задерживает безопасный MVP;
- гарантия предметной корректности action payload приложения.

## 28. Архитектурные запреты

При реализации нельзя:

- добавлять bot token в iframe URL, fragment, JavaScript context или localStorage;
- использовать VoiceRoute cookie внутри Mini App;
- считать client-side disabled button авторизацией;
- проверять voice/role/permission только во время launch;
- позволять Mini App выбирать произвольный `userId`, `applicationId` или `instanceId`;
- использовать last-write-wins без version check для shared state;
- смешивать global Gateway cursor, Mini App realtime cursor и state version;
- считать action completed до commit предметной транзакции;
- публиковать state event до commit;
- хранить полный sensitive payload в audit/metrics;
- разрешать wildcard origins;
- разрешать непроверенные redirects;
- включать camera/microphone автоматически;
- делать Mini App обязательным для использования команд;
- привязывать API к одному демонстрационному типу бота.

## 29. Итог

VoiceRoute Mini Apps должны стать универсальным дополнительным интерфейсом приложения, а
не отдельным видом бота. Команды, interactions, Mini App и внешние интеграции используют
одну предметную логику и одно каноническое состояние. VoiceRoute отвечает за безопасный
запуск, идентичность, контекст, policies, доставку actions, versioned state, realtime
синхронизацию и отзыв доступа; разработчик отвечает за предметную логику и содержимое UI.

Главный критерий качества: два пользователя, открывшие одну instance, видят согласованное
состояние, а любое действие разрешается по актуальным правам в момент выполнения —
независимо от того, было оно инициировано командой или Mini App.
