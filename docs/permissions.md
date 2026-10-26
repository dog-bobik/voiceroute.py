# Permissions и проверки команд

`Permission` содержит полный реестр прав текущего VoiceRoute API, а `Permissions` —
неизменяемый effective-набор. `administrator` автоматически разворачивается во все
известные права.

```python
from voiceroute import Permission, Permissions

permissions = Permissions([Permission.VIEW_CHANNEL, Permission.SEND_MESSAGES])
assert permissions.has(Permission.SEND_MESSAGES)
```

Community и channel DTO содержат рассчитанные сервером права текущего бота. Для
prefix-команд можно потребовать права бота:

```python
from voiceroute import Context, Permission, bot_has_permissions


@bot.command()
@bot_has_permissions(Permission.MANAGE_MESSAGES)
async def cleanup(context: Context) -> None:
    await context.reply("Бот может управлять сообщениями")
```

`@is_owner()` сверяет вызывающего пользователя с актуальным member snapshot.
`@has_permissions(...)` требует exact effective permissions пользователя и работает
по принципу fail closed: если сервер не вернул поле `permissions`, команда не будет
выполнена. Legacy role `moderator` намеренно не считается доказательством конкретного
права.

Для native slash-команд предпочтителен серверный контракт:

```python
@bot.slash_command(
    "cleanup",
    description="Удалить служебные сообщения",
    default_member_permissions=(Permission.MANAGE_MESSAGES,),
)
async def cleanup(context: InteractionContext) -> None:
    await context.respond("Готово", ephemeral=True)
```

VoiceRoute проверяет `defaultMemberPermissions`, актуальные роли, channel/category
overrides, timeout и права бота при показе, доставке и ответе interaction. Локальные
checks улучшают диагностику, но не заменяют повторную проверку сервера.
