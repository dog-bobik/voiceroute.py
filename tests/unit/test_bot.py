from unittest.mock import AsyncMock

import pytest

from voiceroute import Bot, Context, NoChannelsAvailable
from voiceroute.events import MessageUpserted
from voiceroute.models import Channel, Community, Message, User


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
