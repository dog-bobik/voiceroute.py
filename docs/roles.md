# Роли и channel overrides

`client.roles` предоставляет полный bot-compatible контракт ролей VoiceRoute:

- список, создание, изменение и удаление ролей;
- атомарную замену дополнительных ролей участника;
- чтение и изменение channel permission overrides.

```python
role = await client.roles.create(
    community_id,
    "Helpers",
    color="#64c6b5",
    permissions=[Permission.VIEW_CHANNEL, Permission.MANAGE_MESSAGES],
)
await client.roles.set_member_roles(community_id, user_id, [role.id])
```

`set_member_roles` заменяет весь список дополнительных ролей участника. Передавайте и
существующие роли, которые нужно сохранить. Сервер защищает builtin-роли, managed role
приложения, иерархию и запрещает выдавать права, отсутствующие у вызывающего бота.

Пустые `allow` и `deny` удаляют override. Одно право нельзя одновременно разрешить и
запретить:

```python
await client.roles.set_channel_override(
    community_id,
    channel_id,
    PermissionTargetType.ROLE,
    role.id,
    allow=[Permission.SEND_MESSAGES],
    deny=[Permission.ATTACH_FILES],
)
```
