"""Reply with Pong! to new !ping messages."""

import os
from pathlib import Path

from dotenv import load_dotenv

from voiceroute import (
    Bot,
    CachePolicy,
    Context,
    FileCursorStore,
    FileGatewayCheckpointStore,
    Game,
    Intents,
    PlatformEvent,
    Status,
)
from voiceroute.errors import NoChannelsAvailable

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

bot = Bot(
    token=os.environ["VOICEROUTE_BOT_TOKEN"],
    base_url=os.getenv(
        "VOICEROUTE_BASE_URL",
        os.getenv("VOICEROUTE_URL", "https://voiceroute.cc"),
    ),
    cursor_store=FileCursorStore(".voiceroute/cursors.json"),
    gateway_store=FileGatewayCheckpointStore(".voiceroute/gateway.json"),
    intents=Intents.default(),
    cache_policy=CachePolicy(messages=True, max_messages=100),
)


@bot.command()
async def ping(context: Context) -> None:
    await context.reply("Pong!")


@bot.event
async def on_ready() -> None:
    assert bot.user is not None
    transport = "Gateway" if bot.gateway is not None else "legacy SSE"
    print(f"Готово: {bot.user.user.display_name}, transport={transport}")
    if bot.gateway is not None:
        await bot.gateway.change_presence(
            status=Status.ONLINE,
            activities=(Game("/ping"),),
        )


@bot.event
async def on_message_created(event: PlatformEvent) -> None:
    """Gateway signal; the prefix command still receives its full Message over SSE."""
    cached = bot.get_message(
        str(event.data["communityId"]),
        str(event.data["channelId"]),
        str(event.data["messageSeq"]),
    )
    print(f"Gateway MESSAGE_CREATED seq={event.sequence}, cached={cached is not None}")


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
