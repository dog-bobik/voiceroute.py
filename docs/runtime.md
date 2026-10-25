# Жизненный цикл runtime

Один экземпляр `Bot` проходит состояния:

```text
CREATED → STARTING → RUNNING → STOPPING → CLOSED
```

Закрытый экземпляр нельзя запустить повторно: его HTTP client и transport уже освобождены.
Создайте новый `Bot`, если процессу нужен новый запуск.

## Запуск и остановка

```python
bot = Bot(token="...")

task = asyncio.create_task(bot.start())
await bot.wait_until_ready()

# Работа приложения

await bot.stop()
await task
```

`stop()` и `close()` идемпотентны. Одновременные вызовы сериализуются: consumers,
`on_shutdown`, extension teardown и HTTP close выполняются ровно один раз.

`bot.run()` остаётся синхронной точкой входа и использует `asyncio.run()`.

## Инициализация

Для инициализации ресурсов до авторизации переопределите `setup_hook`:

```python
class ApplicationBot(Bot):
    async def setup_hook(self) -> None:
        await self.load_extension("my_bot.extensions.utility")
```

Порядок успешного старта:

```text
setup_hook
→ authenticate
→ channel discovery
→ on_connect
→ state RUNNING
→ on_ready
→ channel consumers
```

`wait_until_ready()` завершается после аутентификации и discovery. Если экземпляр уже
закрыт, метод поднимает `BotClosed`.

## Lifecycle events

```python
@bot.event
async def on_connect() -> None: ...


@bot.event
async def on_ready() -> None: ...


@bot.event
async def on_disconnect(target, error: Exception) -> None: ...


@bot.event
async def on_reconnect(target, delay: float) -> None: ...


@bot.event
async def on_resumed(target) -> None: ...


@bot.event
async def on_shutdown() -> None: ...
```

`on_resumed` в legacy SSE runtime означает начало повторной consumer-сессии после
задержки. После появления Gateway transport тот сможет публиковать более точную семантику
server-confirmed resume отдельным нормализованным событием.

## Supervision

Каждый канал работает в отдельной supervised task. Исключение одного consumer:

1. не отменяет consumers остальных каналов;
2. вызывает `on_disconnect`;
3. сообщает задержку через `on_reconnect`;
4. ждёт exponential backoff;
5. вызывает `on_resumed` и начинает чтение с сохранённого checkpoint.

Задержка начинается с одной секунды, удваивается и ограничивается
`max_consumer_backoff` (по умолчанию 30 секунд). `CancelledError` никогда не превращается
в reconnect: отмена используется для штатной остановки.

Текущий `LegacySSETransport` самостоятельно восстанавливает обычные сетевые разрывы.
Supervisor является внешней защитой от необработанной ошибки transport, cursor store или
event handler.

## Graceful shutdown

Остановка выполняет:

```text
state STOPPING
→ запрет новых доставок
→ cancel channel consumers
→ on_shutdown
→ teardown extensions
→ close HTTP resources
→ state CLOSED
```

Ошибка teardown отдельного расширения записывается стандартным `logging` и не мешает
освободить остальные ресурсы. Bot token, тела сообщений и Authorization headers библиотека
в lifecycle-логи не добавляет.
