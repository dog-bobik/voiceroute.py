"""Regression fence for the public legacy surface during the v1 migration."""

from inspect import signature

from voiceroute import Bot, StreamCheckpoint, VoiceRouteClient


async def test_legacy_client_resources_remain_available() -> None:
    client = VoiceRouteClient(token="vrb_test")

    assert client.application_commands is not None
    assert client.audit is not None
    assert client.automod is not None
    assert client.bots is not None
    assert client.communities is not None
    assert client.events is not None
    assert client.interactions is not None
    assert client.members is not None
    assert client.messages is not None
    assert client.moderation is not None
    assert client.roles is not None
    await client.close()


def test_legacy_bot_constructor_keeps_channel_selection() -> None:
    parameters = signature(Bot).parameters

    assert "community_id" in parameters
    assert "channel_id" in parameters
    assert "event_transport" in parameters
    assert "interaction_event_transport" in parameters


def test_legacy_checkpoint_keeps_sse_and_message_positions_separate() -> None:
    checkpoint = StreamCheckpoint(change_cursor="9007199254740993", message_seq="42")

    assert checkpoint.change_cursor == "9007199254740993"
    assert checkpoint.message_seq == "42"
