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

URL из discovery проверяется до отправки токена: SDK не передаст credential на другой
хост. Смена токена также инвалидирует старую сессию по безопасному fingerprint.

Существующий `Bot` пока продолжает использовать совместимый SSE runtime. Переключение
высокоуровневого диспетчера на Gateway выполняется отдельным этапом, поэтому старые
боты не меняют поведение после обновления зависимости.
