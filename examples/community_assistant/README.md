# Community Assistant Bot

Демонстрационный бот показывает основные возможности `voiceroute.py`: extensions,
prefix- и нативные slash-команды, Gateway events, intents, presence, локальный cache,
interactions, permissions, content API и восстановление checkpoints. Legacy SSE остаётся
включённым только для старых команд, которым нужна полная модель сообщения. Пример не
является частью публичного API библиотеки.

## Установка

Из корня репозитория требуется Python 3.11 или новее:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[examples]'
```

## Настройка

Создайте `.env` в корне репозитория. Не добавляйте этот файл в Git:

```ini
VOICEROUTE_BOT_TOKEN=your-token
VOICEROUTE_BASE_URL=https://voiceroute.cc
VOICEROUTE_COMMUNITY_ID=
VOICEROUTE_CHANNEL_ID=
VOICEROUTE_COMMAND_PREFIX=/
VOICEROUTE_SYNC_APPLICATION_COMMANDS=true
VOICEROUTE_GATEWAY_INTENTS=
VOICEROUTE_GATEWAY_PATH=.voiceroute/community-assistant-gateway.json
```

Обязателен только `VOICEROUTE_BOT_TOKEN`. Если ID не заданы, бот обнаружит все
доступные ему сообщества и текстовые каналы. `VOICEROUTE_CHANNEL_ID` можно указывать
только вместе с `VOICEROUTE_COMMUNITY_ID`. Путь SQLite при необходимости меняется
через `VOICEROUTE_CURSOR_PATH`.

По умолчанию пример открывает Gateway без domain intents: этого достаточно для статуса
online, heartbeat и обработки старых команд через совместимый SSE. Чтобы получать domain
events, сначала включите intents в настройках приложения, а затем перечислите те же
значения через запятую, например:

```ini
VOICEROUTE_GATEWAY_INTENTS=communities,messages,interactions
```

Для `MEMBER_JOINED`, presence других участников и message content также требуется approval
соответствующих privileged intents. SDK проверяет настройки до подключения и завершает
запуск понятной ошибкой, а не циклом reconnect с кодом `4014`.

При `VOICEROUTE_SYNC_APPLICATION_COMMANDS=true` бот во время запуска полностью заменяет
удалённый реестр slash-команд четырьмя определениями из примера. Установите `false`, если
реестром управляет другой процесс.

## Запуск

```bash
python -m examples.community_assistant.bot
```

## Команды

Нативные slash-команды, которые VoiceRoute показывает в подсказках:

- `/ping` — приватно проверяет отклик;
- `/search query private?` — типизированный поиск с публичным или ephemeral-ответом;
- `/whoami` — приватно показывает member snapshot, роли и presence;
- `/capabilities` — показывает effective permissions бота; доступна пользователям с
  `manageMessages`.

Старые prefix-команды оставлены, чтобы пример одновременно показывал оба режима:

- `/help [команда]`, `/ping`, `/about`, `/health`, `/permissions`;
- `/faq`, `/faq <тема>`, `/faq search <запрос>`;
- `/search <запрос>`, `/pins`;
- `/pin [seq]`, `/unpin [seq]`;
- `/react [seq] <emoji>`, `/unreact [seq] <emoji>`;
- `/delete [seq]` — только для сообщения, принадлежащего текущему боту.

Для управляющих команд `seq` можно не указывать: ответьте командой на нужное сообщение.
Например, reply с текстом `/pin` закрепит исходное сообщение, а reply с `/react 👍`
добавит к нему реакцию. Явный `seq` остаётся доступен для автоматизации.

FAQ редактируется в `data/faq.json` без изменения Python-кода.

## Необходимые права

Боту нужен доступ к сообществу и текстовому каналу, чтение истории, отправка сообщений
и `useApplicationCommands`. Для управляющих команд отдельно нужны права на закрепление
сообщений, реакции и удаление собственных сообщений. `/permissions` использует
`@bot_has_permissions`, а `/capabilities` объявляет серверное
`defaultMemberPermissions=manageMessages`.

## Ограничения API

- Поиск и управление сообщениями работают только в текущем канале команды.
- API принимает текст сообщения длиной не более 4000 символов; вывод поиска
  обрезается до этого лимита и максимум десяти результатов.
- Проверка `/delete` ищет целевое сообщение в последних 100 сообщениях. Более старое
  сообщение безопасно отклоняется.
- Effective permissions самого бота доступны в channel DTO. Exact permissions другого
  участника member endpoint пока не возвращает, поэтому небезопасные догадки по legacy
  role не используются; slash-команды проверяет сервер VoiceRoute.
- Один процесс может слушать не более 32 автоматически найденных каналов. Для
  больших установок задайте community/channel ID или разделите нагрузку.

Runtime использует Gateway для lifecycle-событий, presence и cache. Prefix-команды и
текущие slash interactions временно сохраняют совместимые SSE-потоки до их полной
миграции на v1. Gateway checkpoint продвигается только после успешного handler, а cache
откатывается при ошибке, поэтому Resume безопасно повторит необработанное событие.
