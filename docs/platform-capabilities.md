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
```

`await client.platform.require("gateway")` выбрасывает `FeatureUnavailable`, если
функция не объявлена сервером. `await client.platform.current_application()` возвращает
приложение, bot identity и согласованные intents текущего токена.

Режим `api_version="auto"` остаётся значением по умолчанию. Он обнаруживает v1, но не
переключает старые ресурсные методы на новые маршруты самовольно: существующий код
продолжает работать до явной миграции соответствующего API.
