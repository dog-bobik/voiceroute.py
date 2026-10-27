# Возможности платформы

Перед использованием необязательной функции SDK может запросить
`GET /api/v1/capabilities`. Ответ преобразуется в неизменяемую модель и кешируется,
поэтому обработчикам не нужно жёстко привязываться к конкретному развёртыванию VoiceRoute.

```python
from voiceroute import VoiceRouteClient

async with VoiceRouteClient(token="...") as client:
    capabilities = await client.platform.capabilities()
    if capabilities.supports("gateway"):
        print(capabilities.gateway.heartbeat_interval_ms)

    await client.require_feature("gateway")
    status = await client.platform.status()
    if status.degraded:
        print(status.components, status.incidents)

    diagnostics = await client.platform.diagnostics()
    print(diagnostics.unavailable_intents)
```

`await client.platform.require("gateway")` выбрасывает `FeatureUnavailable`, если
функция не объявлена сервером. `await client.platform.current_application()` возвращает
приложение, bot identity и согласованные intents текущего токена.

`status()` кеширует публичный service snapshot не дольше пяти секунд. `refresh()`
принудительно обновляет capabilities и status. `openapi()` и `asyncapi()` всегда читают
runtime contract текущего deployment, а не bundled копию. `diagnostics()` намеренно не
содержит token, session ID или приватные operator-данные.

Режим `api_version="auto"` остаётся значением по умолчанию. Он обнаруживает v1, но не
переключает старые ресурсные методы на новые маршруты самовольно: существующий код
продолжает работать до явной миграции соответствующего API.
