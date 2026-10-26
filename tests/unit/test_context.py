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


async def test_fetch_replied_message_uses_reply_sequence() -> None:
    messages = AsyncMock()
    target = Message(
        seq="41",
        community_id="community-id",
        channel_id="channel-id",
        body="Important",
        author=None,
    )
    messages.history.return_value = MessagePage((target,))
    incoming = Message(
        seq="42",
        community_id="community-id",
        channel_id="channel-id",
        body="/pin",
        author=None,
        reply_to_seq="41",
    )
    context = Context(incoming, "pin", (), messages)

    replied = await context.fetch_replied_message()

    assert context.replied_message_seq == "41"
    assert replied is target
    messages.history.assert_awaited_once_with(
        "community-id",
        "channel-id",
        limit=1,
        after_seq="40",
    )


async def test_fetch_replied_message_without_reply_avoids_request() -> None:
    messages = AsyncMock()
    incoming = Message("42", "community-id", "channel-id", "/pin", None)
    context = Context(incoming, "pin", (), messages)

    assert await context.fetch_replied_message() is None
    messages.history.assert_not_awaited()


async def test_fetch_message_rejects_invalid_sequence() -> None:
    context = Context(
        Message("42", "community-id", "channel-id", "/pin", None),
        "pin",
        (),
        AsyncMock(),
    )

    with pytest.raises(ValueError, match="positive integer"):
        await context.fetch_message("not-a-sequence")


async def test_fetch_member_uses_invoking_channel_visibility() -> None:
    messages = AsyncMock()
    members = AsyncMock()
    members.get.return_value = None
    context = Context(
        Message("42", "community-id", "channel-id", "/whois 42", None),
        "whois",
        ("42",),
        messages,
        members,
    )

    assert await context.fetch_member(42) is None
    members.get.assert_awaited_once_with(
        "community-id",
        42,
        channel_id="channel-id",
    )
