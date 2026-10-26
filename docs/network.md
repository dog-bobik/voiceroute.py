# Сеть, лимиты и повторы

VoiceRoute ограничивает bot API общим лимитом 50 запросов в секунду на бота.
Каждый `VoiceRouteClient` создаёт один sliding-window `RateLimiter`, который
используется resource API и при открытии SSE-соединений.

```python
from voiceroute import RateLimiter, VoiceRouteClient

client = VoiceRouteClient(
    token="...",
    rate_limiter=RateLimiter(limit=50, period=1.0),
)
```

Лимитер координирует только один процесс. Несколько процессов с одинаковым
токеном разделяют серверный лимит, но не локальное состояние; им нужен внешний
распределённый limiter либо консервативные отдельные квоты.

## Политика retry

По умолчанию сетевые ошибки и `503` повторяются только для `GET`, `HEAD` и
`OPTIONS`. Задержка использует exponential backoff с full jitter и ограничена
пятью секундами. Ответ `429` повторяется согласно `Retry-After`, а Bot Platform v1
также может передать задержку в `details.retryAfterMs`.

Изменяющие запросы нельзя безусловно повторять после неопределённого сетевого
результата. Метод отправки сообщения передаёт тот же `clientMessageId` и явно
помечает операцию retryable. Произвольные `POST`, `PATCH` и `DELETE` остаются без
сетевого retry, пока их идемпотентность не доказана контрактом.

Количество попыток задаётся параметром `max_attempts` клиента и по умолчанию
равно трём. Значение включает первоначальный запрос.

Для безопасной mutation можно передать `generate_idempotency_key=True`: SDK создаст UUID
один раз и сохранит тот же ключ и тело во всех попытках одного logical request. Явный
`idempotency_key` и `If-Match` поддерживаются отдельно.

## Защита транспорта

HTTP-клиент не следует redirects с credentials, ограничивает число параллельных запросов
и читает обычный JSON-ответ потоково до заданного предела. Настройки клиента:

- `max_http_concurrency` — по умолчанию 100;
- `max_response_bytes` — по умолчанию 8 MiB;
- `max_attempts` — общее число попыток.

Заголовки `X-VoiceRoute-API-Version`, `X-Request-ID`, `ETag` и rate-limit metadata
доступны через `request_with_response`. Structured v1 errors сохраняют `code`, `details`,
`fieldErrors`, `requestId` и `retryable`.

## SSE

Открытие SSE также проходит через limiter. Разрыв транспорта, `503` и `429`
восстанавливаются с backoff; `Retry-After` имеет приоритет. Ошибки авторизации и
контракта не маскируются бесконечными повторами.
