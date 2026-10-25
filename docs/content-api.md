# Контентный API

`VoiceRouteClient.messages` предоставляет типизированные операции над сообщениями
[VoiceRoute](https://voiceroute.cc). Все `seq` принимаются строками: сервер хранит их как
`bigint`, и преобразование в число может потерять точность.

## Чтение и поиск

```python
page = await client.messages.history(community_id, channel_id, limit=100)
pins = await client.messages.pins(community_id, channel_id)
found = await client.messages.search(community_id, channel_id, "релиз")
```

Методы возвращают `MessagePage`. Для постраничного чтения передавайте
`next_before_seq` предыдущей страницы как `before_seq` следующего запроса.

## Создание и изменение

```python
message = await client.messages.send(
    community_id,
    channel_id,
    "Готово",
    client_message_id=operation_id,
)
message = await client.messages.edit(
    community_id,
    channel_id,
    message.seq,
    "Исправлено",
    version=message.version,
)
await client.messages.delete(community_id, channel_id, message.seq)
```

Для `send` рекомендуется сохранять `client_message_id`: повтор с тем же UUID и тем же
содержимым не создаёт дубликат. Удаление повторяется transport-слоем только при сетевом
сбое и рассматривается как идемпотентная операция. `edit` требует текущую `version`
сообщения и тем самым не затирает конкурентное изменение незаметно.

## Закрепления и реакции

Операции принимают желаемое состояние, а не команду toggle. Это делает безопасным
повтор запроса после разрыва соединения:

```python
await client.messages.set_pin(community_id, channel_id, message.seq, pinned=True)
await client.messages.set_reaction(
    community_id,
    channel_id,
    message.seq,
    "👍",
    active=True,
)
```

Сервер по-прежнему проверяет членство бота, видимость канала и необходимые права.

## Граница проверок

Контрактные тесты библиотеки проверяют HTTP-методы, пути, параметры, тела запросов и
преобразование DTO на локальном mock transport. Они не заменяют live integration tests
с развернутой версией [VoiceRoute](https://voiceroute.cc). При изменении server DTO
сначала обновляется матрица совместимости, затем модели и контрактные fixtures.
