# Community Assistant Bot

Демонстрационный бот показывает актуальный Gateway-first сценарий `voiceroute.py`:
extensions, нативные slash-команды, Gateway events, capabilities, presence, локальный cache,
interactions, permissions, content API и восстановление checkpoints. Пример не зависит
от legacy message SSE и не запрашивает capability `messageContent` для запуска.
Пример не является частью публичного API библиотеки.

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
VOICEROUTE_GATEWAY_CAPABILITIES=messages
VOICEROUTE_COMPONENT_SECRET=replace-with-at-least-16-random-bytes
VOICEROUTE_GATEWAY_PATH=.voiceroute/community-assistant-gateway.json
```

Обязателен только `VOICEROUTE_BOT_TOKEN`. Если ID не заданы, бот обнаружит все
доступные ему сообщества и текстовые каналы. `VOICEROUTE_CHANNEL_ID` можно указывать
только вместе с `VOICEROUTE_COMMUNITY_ID`. Путь SQLite при необходимости меняется
через `VOICEROUTE_CURSOR_PATH`.

По умолчанию пример запрашивает capability `messages`. Она должна присутствовать в
access manifest приложения и быть выдана при установке бота. Нативные команды относятся
к автоматическому семейству `interactions` и отдельной capability не требуют. Чтобы
получать дополнительные domain events, добавьте capabilities в manifest, переустановите
бота и перечислите те же значения через запятую, например:

```ini
VOICEROUTE_GATEWAY_CAPABILITIES=members,messages
```

Не добавляйте `messageContent`: актуальная версия примера не использует prefix-команды.
Grants установки неизменяемы: чтобы расширить их, удалите бота с сервера и установите
снова, подтвердив новый полный список. SDK проверяет manifest и установки до подключения.

`VOICEROUTE_COMPONENT_SECRET` включает демонстрационную `/panel` с подписанной кнопкой.
Секрет должен быть одинаковым на всех экземплярах бота и не должен попадать в Git.

При `VOICEROUTE_SYNC_APPLICATION_COMMANDS=true` бот во время запуска полностью заменяет
удалённый реестр slash-команд из примера. Установите `false`, если
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
- `/panel` — демонстрирует persistent signed button, если задан
  `VOICEROUTE_COMPONENT_SECRET`.

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

Runtime использует Gateway для lifecycle-событий, presence и cache, а interaction
transport — для нативных slash-команд. Gateway checkpoint продвигается только после
успешного handler, а cache откатывается при ошибке, поэтому Resume безопасно повторит
необработанное событие.
