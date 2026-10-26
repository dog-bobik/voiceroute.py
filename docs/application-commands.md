# Нативные команды приложений

VoiceRoute поддерживает зарегистрированные slash-команды и приватные ответы. Реестр
команд приложения заменяется целиком, поэтому перед вызовом `replace` нужно передать
все команды, которые должны остаться активными.

```python
from voiceroute import CommandDefinition, CommandOption, CommandOptionType, VoiceRouteClient

async with VoiceRouteClient(token="...") as client:
    me = await client.bots.get_current()
    await client.application_commands.replace(
        me.application_id,
        [
            CommandDefinition(
                name="echo",
                description="Повторить текст",
                options=(
                    CommandOption(
                        name="text",
                        description="Текст ответа",
                        type=CommandOptionType.STRING,
                        required=True,
                        max_length=1000,
                    ),
                ),
            )
        ],
    )
```

Вызовы доставляются отдельным потоком событий. Его курсор не связан с `message.seq`
или курсорами channel SSE.

```python
from voiceroute import AccessLost, InteractionCreated

async for event in client.events.listen_interactions(cursor="0"):
    if isinstance(event, AccessLost):
        break
    if isinstance(event, InteractionCreated):
        text = str(event.interaction.options["text"])
        await client.interactions.respond(event.interaction.id, text, ephemeral=True)
```

Повтор идентичного ответа идемпотентен. Другой ответ после завершения interaction
возвращает конфликт. Interaction живёт ограниченное время, поэтому его нужно обработать
сразу, а внешние побочные действия дедуплицировать по `interaction.id`.

## Высокоуровневый Bot API

`Bot` может синхронизировать определения при запуске, слушать глобальный interaction
SSE и передавать вызов зарегистрированной функции. Автосинхронизация заменяет удалённый
реестр целиком и поэтому включается явно.

```python
from voiceroute import Bot, CommandOption, CommandOptionType, InteractionContext

bot = Bot(token="...", sync_application_commands=True)


@bot.slash_command(
    "echo",
    description="Повторить текст",
    options=(
        CommandOption(
            name="text",
            description="Текст ответа",
            type=CommandOptionType.STRING,
            required=True,
            max_length=1000,
        ),
    ),
)
async def echo(context: InteractionContext) -> None:
    await context.respond(str(context.options["text"]), ephemeral=True)


bot.run()
```

У global interaction SSE собственный checkpoint. Он сохраняется только после успешной
обработки. Повторно доставленный UUID не запускает callback второй раз в пределах
процесса; внешние действия при нескольких процессах всё равно должны быть идемпотентны.
