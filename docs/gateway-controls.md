# Capabilities, shards и presence

Gateway получает только категории событий, запрошенные через `Capabilities` и выданные
при установке бота. Grants установки неизменяемы; для расширения бот переустанавливается.

```python
from voiceroute import Capabilities, Game, Status, VoiceRouteClient

client = VoiceRouteClient(token="...")
gateway = client.gateway(
    capabilities=Capabilities(messages=True, message_content=True, members=True),
)

await gateway.change_presence(status=Status.ONLINE, activities=[Game("/help")])
```

Для больших установок `client.shards(4)` создаёт четыре shard-сессии. Параметр
`shard_ids=(0, 2)` позволяет распределить выбранные shards по отдельным процессам, а
`ShardManager` разносит Identify по времени.

После подключения доступны управляющие операции:

- `change_presence()` — статус и до четырёх activities;
- `request_members()` — ограниченная страница участников, ответ приходит событием
  `MEMBERS_CHUNK`;
- `update_subscriptions()` — замена набора durable subscriptions текущей сессии.
