from unittest.mock import AsyncMock

from voiceroute.commands import Context
from voiceroute.models import Message


async def test_reply_uses_stable_operation_id() -> None:
    messages = AsyncMock()
    messages.send.return_value = Message(
        seq="18",
        community_id="community-id",
        channel_id="channel-id",
        body="Pong!",
        author=None,
    )
    incoming = Message(
        seq="17",
        community_id="community-id",
        channel_id="channel-id",
        body="!ping",
        author=None,
    )

    first = Context(incoming, "ping", (), messages)
    second = Context(incoming, "ping", (), messages)
    await first.reply("Pong!")
    await second.reply("Pong!")

    first_id = messages.send.await_args_list[0].kwargs["client_message_id"]
    second_id = messages.send.await_args_list[1].kwargs["client_message_id"]
    assert first_id == second_id
