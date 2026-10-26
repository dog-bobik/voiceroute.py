# Контрактные модели

Каталог событий в `voiceroute.models.PlatformEventType` генерируется из официального
`docs/bot-platform/capabilities.json`. Это исключает ручное расхождение имён событий с
сервером.

```bash
python scripts/generate_event_types.py \
  ../VoiceRoute/docs/bot-platform/capabilities.json \
  src/voiceroute/models/generated_events.py
```

Флаг `--check` подходит для CI и завершает команду с ошибкой, если checked-in файл
устарел.

`PlatformEvent` намеренно допускает неизвестное имя события и сохраняет исходный
словарь. Благодаря этому добавление события на сервере не ломает старую версию SDK.
Поля `sequence` и идентификаторы остаются строками: их нельзя безопасно приводить к
числам во всех поддерживаемых языках.
