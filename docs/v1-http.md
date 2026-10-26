# HTTP transport Bot Platform v1

Новый transport сохраняет совместимость с legacy API и дополнительно понимает контракт
`/api/v1`: structured errors, request ID, ETag, idempotency и rate-limit metadata.

Обычные resource API по-прежнему получают только JSON payload. Для условных мутаций и
диагностики доступен `request_with_response()`, возвращающий также `etag`, `request_id`,
версию API и текущий rate-limit bucket.

Повтор небезопасной мутации разрешается только при наличии стабильного
`Idempotency-Key`. Один логический retry обязан повторно использовать тот же ключ.
Конфликт `If-Match` представлен исключением `ResourceVersionConflict`, а неизвестные
серверные error codes сохраняются в `HTTPError.code`.
