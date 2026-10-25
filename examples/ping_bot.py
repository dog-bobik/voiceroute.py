"""Reply with Pong! to new !ping messages."""

import os

from voiceroute import Bot, Context

bot = Bot(
    token=os.environ["VOICEROUTE_BOT_TOKEN"],
    base_url=os.getenv("VOICEROUTE_URL", "https://voiceroute.cc"),
)


@bot.command()
async def ping(context: Context) -> None:
    await context.reply("Pong!")


@bot.event
async def on_ready() -> None:
    assert bot.user is not None
    print(f"Готово: {bot.user.user.display_name}")


@bot.event
async def on_error(error: Exception) -> None:
    print(f"Ошибка обработчика: {error}")


bot.run()
