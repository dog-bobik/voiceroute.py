# Участники сообщества

Bot token может читать активных участников сообщества. Необязательный `channel_id`
ограничивает результат участниками, которым доступен конкретный канал.

```python
async with VoiceRouteClient(token="...") as client:
    members = await client.members.list("community-id", channel_id="channel-id")
    alice = await client.members.get("community-id", 42)
```

`Member` содержит пользователя, legacy role, назначенные роли, nickname, pending,
версию ресурса, timeout и рассчитанные сервером признаки `can_ban` и `can_timeout` для
текущего бота. Эти признаки являются snapshot: сервер всё равно повторно проверяет
права при мутации.

При v1 `get()` делает точечный запрос, а `list_page()` и `search()` возвращают одну
cursor-страницу. `iter_members()` и `iter_search()` обходят страницы лениво. `list()`
сохраняет удобный режим загрузки всего списка, используя cursor pagination под капотом.
В legacy режиме `get()` остаётся поиском в полном актуальном снимке.

Для изменения v1 member передайте версию из `Member.version` как `if_match`:

```python
member = await client.members.get(community_id, user_id)
if member is None or member.version is None:
    raise RuntimeError("Member is unavailable or has no v1 version")
updated = await client.members.update_v1(
    community_id,
    user_id,
    if_match=member.version,
    nickname="Новый ник",
    reason="Profile request",
)
```

В prefix-команде можно получить участника с учётом видимости текущего канала:

```python
@bot.command()
async def whois(context: Context, user_id: int) -> None:
    member = await context.fetch_member(user_id)
    await context.reply(member.display_name if member else "Участник не найден")
```

В native command `await context.fetch_member()` без аргумента возвращает вызвавшего
команду участника. Наличие snapshot endpoint не создаёт событие `on_member_join`.
