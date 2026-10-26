# Модерация участников

`client.moderation` предоставляет типизированный интерфейс к модерации
[VoiceRoute](https://voiceroute.cc): список доступных целей, активные ограничения,
исключение, блокировка и таймаут.

```python
snapshot = await client.moderation.snapshot(community_id)

for member in snapshot.items:
    if member.can_timeout:
        await client.moderation.timeout(
            community_id,
            member.user.id,
            10 * 60,
            reason="Флуд",
        )
```

Доступные операции:

- `current_timeout()` — активный таймаут самого бота;
- `snapshot()` — участники и допустимые для текущего бота действия;
- `bans()` — список блокировок;
- `kick()`, `ban()`, `unban()`;
- `timeout()` и `remove_timeout()`.

Библиотека заранее проверяет серверные пределы: таймаут от одной секунды до 28 дней,
причина — не более 512 символов. Окончательное решение всё равно принимает сервер с
учётом permissions и иерархии ролей.
