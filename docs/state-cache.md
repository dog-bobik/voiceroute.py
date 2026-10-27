# Cache и восстановление состояния

`Bot` поддерживает typed snapshots сообществ, категорий, каналов, ролей, участников,
тредов, polls, expressions, bans, voice states и installations.
Message cache выключен по умолчанию и включается с явным ограничением:

```python
from voiceroute import Bot, CachePolicy

bot = Bot(
    token="...",
    cache_policy=CachePolicy(messages=True, max_messages=500),
)

member = bot.get_member(community_id, user_id)  # только локальный cache
member = await bot.fetch_member(community_id, user_id)  # запрос REST
```

`get_*()` никогда не выполняет скрытый сетевой запрос. Полный REST fetch всегда явно
помечен `await fetch_*()`. Для известных полных snapshots доступны `to_domain()`
converters, а новые домены представлены `CachedResource` без потери raw fields.

`max_per_domain` ограничивает каждый домен отдельным LRU, а `max_messages` независимо
ограничивает opt-in message cache:

```python
CachePolicy(messages=True, max_messages=500, max_per_domain=10_000)
```

Сигнальные Gateway payload не притворяются полными ресурсами. `CachedEntity.partial`
остаётся `True`, пока snapshot не получен через REST/reconciliation; флаг `redacted`
показывает сознательно скрытые сервером данные.

Для update-событий доступны snapshots до и после изменения:

```python
@bot.event
async def on_role_update(before, after):
    print(before.name, "->", after.name)
```

После close code, запрещающего Resume, SDK очищает потенциально недостоверное состояние
и восстанавливает доступные communities/channels/roles/members через REST. Политику
первичной синхронизации можно включить через `CachePolicy(reconcile_on_ready=True)`.
