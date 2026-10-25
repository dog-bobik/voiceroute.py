from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from voiceroute import VoiceRouteClient

BASE_PATH = "https://voiceroute.cc/api/communities/community-id/channels/channel-id/messages"


def message_payload(*, body: str = "Pong!", client_message_id: str = "operation-id") -> dict:
    return {
        "seq": "17",
        "communityId": "community-id",
        "channelId": "channel-id",
        "body": body,
        "clientMessageId": client_message_id,
        "author": {
            "id": 42,
            "username": "bot_example",
            "displayName": "Example",
            "bot": True,
        },
    }


@respx.mock
async def test_send_message_uses_provided_idempotency_identifier() -> None:
    route = respx.post(BASE_PATH).mock(
        return_value=httpx.Response(201, json={"message": message_payload()})
    )

    async with VoiceRouteClient(token="vrb_secret") as client:
        message = await client.messages.send(
            "community-id",
            "channel-id",
            "Pong!",
            client_message_id="operation-id",
        )

    assert route.calls[0].request.read()
    assert b'"clientMessageId":"operation-id"' in route.calls[0].request.content
    assert message.seq == "17"


@respx.mock
async def test_history_passes_string_cursor() -> None:
    route = respx.get(BASE_PATH).mock(
        return_value=httpx.Response(
            200,
            json={"items": [message_payload()], "nextBeforeSeq": "10"},
        )
    )

    async with VoiceRouteClient(token="vrb_secret") as client:
        page = await client.messages.history(
            "community-id", "channel-id", after_seq="9007199254740993"
        )

    assert route.calls[0].request.url.params["afterSeq"] == "9007199254740993"
    assert "beforeSeq" not in route.calls[0].request.url.params
    assert page.next_before_seq == "10"


async def test_history_rejects_conflicting_cursors() -> None:
    async with VoiceRouteClient(token="vrb_secret") as client:
        with pytest.raises(ValueError, match="cannot be used together"):
            await client.messages.history(
                "community-id",
                "channel-id",
                before_seq="10",
                after_seq="20",
            )


async def test_send_rejects_empty_message() -> None:
    async with VoiceRouteClient(token="vrb_secret") as client:
        with pytest.raises(ValueError, match="must contain"):
            await client.messages.send("community-id", "channel-id")


@respx.mock
async def test_idempotent_send_retries_network_failure_with_same_body() -> None:
    route = respx.post(BASE_PATH).mock(
        side_effect=[
            httpx.ConnectError("connection lost"),
            httpx.Response(201, json={"message": message_payload()}),
        ]
    )

    with patch("voiceroute.transport.http.asyncio.sleep", new=AsyncMock()):
        async with VoiceRouteClient(token="vrb_secret") as client:
            await client.messages.send(
                "community-id",
                "channel-id",
                "Pong!",
                client_message_id="operation-id",
            )

    assert route.call_count == 2
    assert route.calls[0].request.content == route.calls[1].request.content
