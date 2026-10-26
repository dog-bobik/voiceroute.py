# AutoMod

`client.automod` управляет полной конфигурацией автоматической модерации
[VoiceRoute](https://voiceroute.cc).

```python
from voiceroute import AutoModConfig

config = AutoModConfig(
    enabled=True,
    blocked_words=("спам", "реклама"),
    max_mentions=5,
    spam_limit=5,
    block_duplicates=True,
    slowmode_seconds=10,
)
saved = await client.automod.update(community_id, config)
```

Текущие настройки доступны через `await client.automod.get(community_id)`. Метод
`update()` принимает полную конфигурацию, нормализует и удаляет дубликаты запрещённых
слов, а также проверяет все серверные лимиты до HTTP-запроса.
