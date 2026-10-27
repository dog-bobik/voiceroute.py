# Голосовые сессии

Voice transport доступен только на deployment, который объявляет
`features.voiceTransport=true`. Приложению нужны scopes `bot`, `voice.connect`,
`voice.transmit`, одобренный privileged intent `voiceStates` и права канала
`viewChannel`, `connect`, `speak`.

Установите optional media runtime:

```bash
python -m pip install 'voiceroute.py[voice]'
```

Gateway должен быть запущен с voice intent. Состояние участника можно найти через REST,
после чего `VoiceSession` выполнит opcode 4, проверит media origin и подключится к LiveKit:

```python
from voiceroute import Intents, VoiceSession

intents = Intents(communities=True, messages=True, voice_states=True)
gateway = client.gateway(intents=intents)

channel_id = await client.voice.find_member_channel(community_id, user_id)
if channel_id is None:
    raise RuntimeError("Пользователь не находится в голосовом канале")

async with VoiceSession(
    gateway,
    allowed_media_origins=("https://voiceroute.cc",),
) as voice:
    await voice.join(community_id, channel_id, transmit=True)
    await voice.write_pcm(samples)  # ровно 960 signed 16-bit mono samples
    await voice.drain()
```

Один PCM frame содержит 20 ms: 960 mono samples при 48 kHz. Media token остаётся внутри
сессии и не должен логироваться или сохраняться. `allowed_media_origins` задаётся явно,
чтобы скомпрометированный discovery/event не мог передать credential на другой origin.

Текущий Python adapter покрывает исходящую передачу. Controlled receive WebSocket и
административная voice policy остаются отдельным следующим срезом.
