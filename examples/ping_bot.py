"""Reply with Pong! to new !ping messages."""

import os
from pathlib import Path

from dotenv import load_dotenv

from voiceroute import Bot, Context
from voiceroute.errors import NoChannelsAvailable

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

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


try:
    bot.run()
except NoChannelsAvailable as error:
    raise SystemExit(
        "Бот не видит текстовых каналов. Установите его в сообщество VoiceRoute "  # noqa: RUF001
        "и выдайте права viewChannel, readMessageHistory и sendMessages."
    ) from error
