# Единый диспетчер событий

В режиме `event_transport="auto"` бот проверяет capabilities и выбирает Gateway, когда
он доступен. `event_transport="sse"` оставляет прежний runtime, а `"gateway"` включает
новый транспорт явно.

Каждое Gateway-событие доступно по имени из AsyncAPI:

```python
from voiceroute import Bot, Intents, PlatformEvent

bot = Bot(token="...", intents=Intents(messages=True, members=True))

@bot.event
async def on_member_joined(event: PlatformEvent):
    print(event.data["userId"])

@bot.event
async def on_raw_event(event: PlatformEvent):
    print(event.name, event.sequence)
```

`await bot.wait_for("MESSAGE_CREATED", check=..., timeout=30)` ожидает одно событие без
постоянного listener. Delivery ID защищает обработчики от повторной доставки. Неизвестное
будущей версии событие приходит в `on_raw_event` и `on_unknown_event`, не обрывая сессию.

Если listener падает и нет `on_event_error` либо `on_error`, исключение доходит до
Gateway: checkpoint не продвигается, поэтому событие можно получить снова после Resume.

Legacy `on_message(Message)` продолжает принимать полную старую модель через SSE.
Gateway-события сообщений пока приходят отдельно как `on_message_created(PlatformEvent)`:
их payload является сигналом изменения, а полная объектная модель будет получаться через
cache/reconciliation и новые message endpoints без подмены старого контракта.
