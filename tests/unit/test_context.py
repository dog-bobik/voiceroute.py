import uuid
from unittest.mock import AsyncMock

import pytest

from voiceroute.commands import Context
from voiceroute.errors import Conflict, TransportError
from voiceroute.models import Message, MessagePage


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


async def test_failed_reply_reuses_operation_id_on_retry() -> None:
    messages = AsyncMock()
    messages.send.side_effect = [
        TransportError("connection lost"),
        Message(
            seq="18",
            community_id="community-id",
            channel_id="channel-id",
            body="Pong!",
            author=None,
        ),
    ]
    incoming = Message(
        seq="17",
        community_id="community-id",
        channel_id="channel-id",
        body="!ping",
        author=None,
    )
    context = Context(incoming, "ping", (), messages)

    with pytest.raises(TransportError):
        await context.reply("Pong!")
    await context.reply("Pong!")

    first_id = messages.send.await_args_list[0].kwargs["client_message_id"]
    retry_id = messages.send.await_args_list[1].kwargs["client_message_id"]
    assert retry_id == first_id


async def test_conflicting_reply_recovers_existing_idempotent_message() -> None:
    messages = AsyncMock()
    incoming = Message(
        seq="17",
        community_id="community-id",
        channel_id="channel-id",
        body="!ping",
        author=None,
    )
    context = Context(incoming, "ping", (), messages)
    messages.send.side_effect = Conflict(409, "identifier already used")

    operation_id = uuid.uuid5(
        uuid.UUID("88769cac-916c-4a4a-a370-a1f971729e7b"),
        "community-id:channel-id:17:ping:0",
    )
    existing = Message(
        seq="18",
        community_id="community-id",
        channel_id="channel-id",
        body="Pong! Обработка: 0.01 мс",
        author=None,
        client_message_id=str(operation_id),
    )
    messages.history.return_value = MessagePage((existing,))

    recovered = await context.reply("Pong! Обработка: 0.02 мс")

    assert recovered is existing
    messages.history.assert_awaited_once_with(
        "community-id",
        "channel-id",
        limit=100,
        before_seq=None,
    )


async def test_unresolved_conflict_advances_error_reply_index() -> None:
    messages = AsyncMock()
    messages.send.side_effect = [
        Conflict(409, "identifier already used"),
        Message(
            seq="19",
            community_id="community-id",
            channel_id="channel-id",
            body="Ошибка",
            author=None,
        ),
    ]
    messages.history.return_value = MessagePage(())
    incoming = Message(
        seq="17",
        community_id="community-id",
        channel_id="channel-id",
        body="!ping",
        author=None,
    )
    context = Context(incoming, "ping", (), messages)

    with pytest.raises(Conflict):
        await context.reply("Pong!")
    await context.reply("Ошибка")

    first_id = messages.send.await_args_list[0].kwargs["client_message_id"]
    error_id = messages.send.await_args_list[1].kwargs["client_message_id"]
    assert error_id != first_id
