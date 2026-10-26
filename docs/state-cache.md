# Cache и восстановление состояния

`Bot` поддерживает локальные snapshots сообществ, каналов, ролей, участников и тредов.
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
