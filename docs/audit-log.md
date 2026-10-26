# Журнал аудита

`client.audit` читает неизменяемый журнал действий сообщества
[VoiceRoute](https://voiceroute.cc). Доступ регулируется permission `viewAuditLog`.

```python
page = await client.audit.list(
    community_id,
    action="member.ban",
    actor_id=moderator_id,
    limit=50,
)

while page.next_before is not None:
    page = await client.audit.list(
        community_id,
        before=page.next_before,
        limit=50,
    )
```

Каждая `AuditEntry` содержит действие и локализованную подпись, автора, цель,
причину, безопасные снимки состояния `before`/`after` и время. `AuditPage` также
возвращает доступные фильтры авторов и действий, следующий курсор и срок хранения.
Курсор остаётся строкой, поэтому большие серверные идентификаторы не теряют точность.
