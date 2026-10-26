# Участники сообщества

Bot token может читать активных участников сообщества. Необязательный `channel_id`
ограничивает результат участниками, которым доступен конкретный канал.

```python
async with VoiceRouteClient(token="...") as client:
    members = await client.members.list("community-id", channel_id="channel-id")
    alice = await client.members.get("community-id", 42)
```

`Member` содержит пользователя, legacy role, назначенные роли, позицию высшей роли,
presence, timeout и рассчитанные сервером признаки `can_ban` и `can_timeout` для
текущего бота. Эти признаки являются snapshot: сервер всё равно повторно проверяет
права при мутации.

В prefix-команде можно получить участника с учётом видимости текущего канала:

```python
@bot.command()
async def whois(context: Context, user_id: int) -> None:
    member = await context.fetch_member(user_id)
    await context.reply(member.display_name if member else "Участник не найден")
```

В native command `await context.fetch_member()` без аргумента возвращает вызвавшего
команду участника. Текущий сервер не предоставляет отдельный маршрут одного участника
или пагинацию, поэтому `get` ищет пользователя в актуальном списке активных участников.
Наличие snapshot endpoint не создаёт событие `on_member_join`.
