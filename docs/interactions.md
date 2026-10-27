# Rich interactions

`InteractionContext` соблюдает трёхсекундный deadline начального callback и предоставляет:

- `send_message()` / `respond()`;
- `defer()`;
- `autocomplete()`;
- `show_modal()`;
- `followup()`;
- `edit_original()` и `delete_original()`.

В `BOT_DM` и `PRIVATE_CHANNEL` ответы по умолчанию ephemeral. Явный `ephemeral=` может
изменить это поведение там, где его допускает сервер.

```python
from voiceroute import ActionRow, ButtonStyle, Component

bot = Bot(token="...", component_secret="at-least-16-bytes")

@bot.component("refresh")
async def refresh(context, payload):
    await context.send_message(f"Обновлено: {payload}", ephemeral=True)

custom_id = bot.components.custom_id("refresh", "dashboard")
row = ActionRow((Component(
    type="BUTTON",
    custom_id=custom_id,
    style=ButtonStyle.PRIMARY,
    label="Обновить",
),))
```

Signed `custom_id` содержит route и небольшой payload, переживает рестарт процесса и
проверяется через HMAC. Секрет должен быть одинаковым на всех instances и не должен
попадать в исходный код или логи. Interaction token скрыт из `repr`, не сохраняется в
cursor/checkpoint stores и используется только для callback/follow-up HTTP-запросов.
