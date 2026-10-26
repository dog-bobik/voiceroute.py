# Gateway WebSocket

Bot Platform v1 доставляет события через Gateway. REST остаётся способом читать и
изменять ресурсы, а WebSocket становится основным realtime-транспортом.

```python
from voiceroute import FileGatewayCheckpointStore, VoiceRouteClient

client = VoiceRouteClient(token="...")
gateway = client.gateway(
    intents=("messages", "members"),
    store=FileGatewayCheckpointStore(".data/gateway.json"),
)

async def handle(event):
    print(event.name, event.data)

await gateway.run(handle)
```

Клиент выполняет discovery, проверяет capability `gateway`, отправляет Identify или
Resume, поддерживает heartbeat и переподключается с ограниченной экспоненциальной
задержкой. Checkpoint сохраняется только после успешного завершения `handle`, поэтому
ошибка бизнес-логики не подтверждает необработанное событие.

Domain handlers выполняются через ограниченную очередь отдельно от reader-loop. Поэтому
долгий handler не задерживает heartbeat ACK, server reconnect и другие control frames.
Переподключение использует full jitter, а session-start limit проверяется до Identify.

URL из discovery проверяется до отправки токена: SDK не передаст credential на другой
хост. Смена токена также инвалидирует старую сессию по безопасному fingerprint.

Для нескольких процессов доступны `RedisGatewayCheckpointStore` и
`PostgreSQLGatewayCheckpointStore`. Чтобы один shard не запустился одновременно в двух
процессах, передайте `RedisGatewayCheckpointCoordinator`; lease продлевается heartbeat и
освобождается при корректной остановке. `metric_hook` получает безопасные runtime-метрики
без токена и session ID.

`Bot` в режиме `auto` использует Gateway, когда сервер объявляет capability. Совместимые
SSE-потоки запускаются параллельно только для зарегистрированных старых prefix- и
application-command handlers, пока их полные payload не перенесены на v1.
