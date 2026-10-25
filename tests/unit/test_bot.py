from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest

from voiceroute import Bot, Context, MemoryCursorStore, NoChannelsAvailable
from voiceroute.bot import ChannelTarget
from voiceroute.events import MessageUpserted
from voiceroute.models import Channel, Community, Message, MessagePage, User


def incoming_message(body: str, *, bot: bool = False, edited: bool = False) -> Message:
    return Message(
        seq="17",
        community_id="community-id",
        channel_id="channel-id",
        body=body,
        author=User(7, "member", "Member", bot=bot),
        edited_at="2026-10-25T00:00:00Z" if edited else None,
    )


async def test_command_receives_parsed_arguments() -> None:
    runtime = Bot(
        token="vrb_secret",
        community_id="community-id",
        channel_id="channel-id",
    )
    captured: list[Context] = []

    @runtime.command()
    async def echo(context: Context) -> None:
        captured.append(context)

    await runtime._handle_message(MessageUpserted(incoming_message('!echo "hello world"'), "1"))
    await runtime.close()

    assert captured[0].args == ("hello world",)


@pytest.mark.parametrize("body", ["/ping", "!ping"])
async def test_default_command_prefixes_accept_slash_and_bang(body: str) -> None:
    runtime = Bot(token="vrb_secret")
    handler = AsyncMock()
    runtime.command("ping")(handler)

    await runtime._handle_message(MessageUpserted(incoming_message(body), "1"))
    await runtime.close()

    handler.assert_awaited_once()


@pytest.mark.parametrize("bot,edited", [(True, False), (False, True)])
async def test_command_ignores_bots_and_edits(bot: bool, edited: bool) -> None:
    runtime = Bot(
        token="vrb_secret",
        community_id="community-id",
        channel_id="channel-id",
    )
    handler = AsyncMock()
    runtime.command("ping")(handler)

    await runtime._handle_message(
        MessageUpserted(incoming_message("!ping", bot=bot, edited=edited), "1")
    )
    await runtime.close()

    handler.assert_not_awaited()


async def test_duplicate_command_registration_is_rejected() -> None:
    runtime = Bot(
        token="vrb_secret",
        community_id="community-id",
        channel_id="channel-id",
    )

    @runtime.command("ping")
    async def first(context: Context) -> None:
        pass

    with pytest.raises(ValueError, match="already registered"):

        @runtime.command("ping")
        async def second(context: Context) -> None:
            pass

    await runtime.close()


async def test_discovers_text_channels_across_communities() -> None:
    runtime = Bot(token="vrb_secret")
    runtime.client.communities.list = AsyncMock(
        return_value=[Community("first", "First"), Community("second", "Second")]
    )
    runtime.client.communities.list_channels = AsyncMock(
        side_effect=[
            [Channel("text-1", "general", "text"), Channel("voice-1", "Voice", "voice")],
            [Channel("text-2", "chat", "TEXT")],
        ]
    )

    targets = await runtime._discover_channels()
    await runtime.close()

    assert [(target.community_id, target.channel_id) for target in targets] == [
        ("first", "text-1"),
        ("second", "text-2"),
    ]


async def test_explicit_channel_skips_discovery() -> None:
    runtime = Bot(
        token="vrb_secret",
        community_id="community-id",
        channel_id="channel-id",
    )

    targets = await runtime._discover_channels()
    await runtime.close()

    assert targets[0].channel_id == "channel-id"


async def test_empty_discovery_has_actionable_error() -> None:
    runtime = Bot(token="vrb_secret")
    runtime.client.communities.list = AsyncMock(return_value=[])

    with pytest.raises(NoChannelsAvailable, match="not installed"):
        await runtime._discover_channels()
    await runtime.close()


def test_run_treats_keyboard_interrupt_as_graceful_shutdown() -> None:
    runtime = Bot(token="vrb_secret")

    def interrupt(coroutine: object) -> None:
        coroutine.close()  # type: ignore[attr-defined]
        raise KeyboardInterrupt

    with patch("voiceroute.bot.asyncio.run", side_effect=interrupt):
        runtime.run()


async def test_channel_consumer_requests_initial_replay() -> None:
    runtime = Bot(token="vrb_secret")
    runtime.client.messages.history = AsyncMock(return_value=MessagePage(()))
    captured: dict[str, str | None] = {}

    async def stream(
        community_id: str,
        channel_id: str,
        *,
        after_seq: str | None = None,
        cursor: str | None = None,
    ):
        captured["community_id"] = community_id
        captured["channel_id"] = channel_id
        captured["after_seq"] = after_seq
        captured["cursor"] = cursor
        if False:
            yield None

    runtime.client.events.listen_messages = stream  # type: ignore[method-assign]
    await runtime._consume_channel(ChannelTarget("community-id", "channel-id"))
    await runtime.close()

    assert captured == {
        "community_id": "community-id",
        "channel_id": "channel-id",
        "after_seq": "0",
        "cursor": None,
    }


async def test_channel_consumer_checkpoints_only_after_success() -> None:
    store = MemoryCursorStore()
    runtime = Bot(token="vrb_secret", cursor_store=store)
    runtime.client.messages.history = AsyncMock(return_value=MessagePage(()))
    target = ChannelTarget("community-id", "channel-id")
    event = MessageUpserted(incoming_message("hello"), "83")

    async def stream(*args, **kwargs):
        yield event

    runtime.client.events.listen_messages = stream  # type: ignore[method-assign]
    runtime._handle_message = AsyncMock()  # type: ignore[method-assign]

    await runtime._consume_channel(target)
    checkpoint = await store.load(runtime._stream_key(target))
    await runtime.close()

    assert checkpoint is not None
    assert checkpoint.change_cursor == "83"
    assert checkpoint.message_seq == "17"


async def test_failed_handler_does_not_advance_checkpoint() -> None:
    store = MemoryCursorStore()
    runtime = Bot(token="vrb_secret", cursor_store=store)
    runtime.client.messages.history = AsyncMock(return_value=MessagePage(()))
    target = ChannelTarget("community-id", "channel-id")

    async def stream(*args, **kwargs):
        yield MessageUpserted(incoming_message("hello"), "83")

    runtime.client.events.listen_messages = stream  # type: ignore[method-assign]
    runtime._handle_message = AsyncMock(side_effect=RuntimeError("handler failed"))  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="handler failed"):
        await runtime._consume_channel(target)
    checkpoint = await store.load(runtime._stream_key(target))
    await runtime.close()

    assert checkpoint is None


async def test_history_catch_up_reads_every_page() -> None:
    store = MemoryCursorStore()
    runtime = Bot(token="vrb_secret", cursor_store=store)
    target = ChannelTarget("community-id", "channel-id")
    messages = [replace(incoming_message("hello"), seq=str(index)) for index in range(1, 206)]
    runtime.client.messages.history = AsyncMock(
        side_effect=[
            MessagePage(tuple(messages[:100])),
            MessagePage(tuple(messages[100:200])),
            MessagePage(tuple(messages[200:])),
        ]
    )
    runtime._handle_message = AsyncMock()  # type: ignore[method-assign]

    final_seq = await runtime._catch_up_history(target, runtime._stream_key(target), "0")
    checkpoint = await store.load(runtime._stream_key(target))
    await runtime.close()

    assert final_seq == "205"
    assert checkpoint is not None and checkpoint.message_seq == "205"
    assert [
        call.kwargs["after_seq"] for call in runtime.client.messages.history.await_args_list
    ] == [
        "0",
        "100",
        "200",
    ]
    assert runtime._handle_message.await_count == 205
