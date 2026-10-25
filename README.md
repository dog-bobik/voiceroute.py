# voiceroute.py

Асинхронный Python SDK и фреймворк для разработки ботов в
[VoiceRoute](https://voiceroute.cc).

> [!WARNING]
> Проект находится на ранней стадии разработки. Публичный API может меняться до
> выпуска версии `1.0.0`.

## Цели проекта

- типизированный асинхронный клиент HTTP API;
- надёжная обработка SSE с восстановлением курсора;
- идемпотентная отправка сообщений;
- удобная событийная модель и команды в стиле современных bot-фреймворков;
- расширяемая архитектура без смешивания bot token и пользовательской сессии;
- безопасная работа с лимитами запросов, повторными попытками и секретами.

## Установка для разработки

Требуется Python 3.11 или новее.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Минимальный пример

```python
import asyncio
import os

from voiceroute import VoiceRouteClient


async def main() -> None:
    async with VoiceRouteClient(token=os.environ["VOICEROUTE_BOT_TOKEN"]) as client:
        identity = await client.bots.get_current()
        print(identity.user.display_name)


asyncio.run(main())
```

Полноценный `Bot` API, обработчики событий и команды будут добавлены после
стабилизации HTTP transport и SSE.

## Состояние реализации

| Возможность | Состояние |
| --- | --- |
| Bot-аутентификация | Основа готова |
| Профиль текущего бота | Основа готова |
| Сообщества и каналы | Запланировано |
| Сообщения | Запланировано |
| SSE и восстановление курсора | Запланировано |
| Команды и middleware | Запланировано |
| Треды, вложения и реакции | Запланировано |
| Роли и модерация | Запланировано |
| Голос для сторонних ботов | Не поддерживается API [VoiceRoute](https://voiceroute.cc) |

Подробная последовательность работ находится в [дорожной карте](docs/roadmap.md),
а принятые границы проекта — в [описании архитектуры](docs/architecture.md).

## Разработка

```bash
ruff check .
ruff format --check .
mypy src
pytest --cov=voiceroute --cov-report=term-missing
```

Правила веток, коммитов и слияний описаны в [CONTRIBUTING.md](CONTRIBUTING.md).

## Безопасность

Не добавляйте bot token в исходный код, URL, query-параметры или логи. Используйте
переменные окружения и передавайте токен только через официальный заголовок
авторизации. Инструкции по сообщению об уязвимостях находятся в
[SECURITY.md](SECURITY.md).

## Лицензия

[MIT](LICENSE)

