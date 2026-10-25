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
        "version": 3,
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


@respx.mock
async def test_edit_message_uses_channel_scoped_resource() -> None:
    route = respx.patch(f"{BASE_PATH}/17").mock(
        return_value=httpx.Response(200, json={"message": message_payload(body="Updated")})
    )

    async with VoiceRouteClient(token="vrb_secret") as client:
        message = await client.messages.edit(
            "community-id", "channel-id", "17", "Updated", version=3
        )

    assert message.body == "Updated"
    assert route.calls[0].request.content == b'{"body":"Updated","version":3}'


@respx.mock
async def test_delete_message_accepts_empty_response() -> None:
    route = respx.delete(f"{BASE_PATH}/17").mock(return_value=httpx.Response(204))

    async with VoiceRouteClient(token="vrb_secret") as client:
        await client.messages.delete("community-id", "channel-id", "17")

    assert route.called


@pytest.mark.parametrize(
    ("method", "suffix", "call", "expected_body"),
    [
        (
            "put",
            "17/pin",
            lambda client: client.messages.set_pin(
                "community-id", "channel-id", "17", pinned=False
            ),
            b'{"pinned":false}',
        ),
        (
            "put",
            "17/reactions",
            lambda client: client.messages.set_reaction(
                "community-id", "channel-id", "17", "👍", active=True
            ),
            b'{"emoji":"\xf0\x9f\x91\x8d","active":true}',
        ),
    ],
)
@respx.mock
async def test_message_state_mutations_use_explicit_desired_state(
    method, suffix, call, expected_body
) -> None:
    route = getattr(respx, method)(f"{BASE_PATH}/{suffix}").mock(
        return_value=httpx.Response(200, json={"message": message_payload()})
    )

    async with VoiceRouteClient(token="vrb_secret") as client:
        await call(client)

    assert route.calls[0].request.content == expected_body


@pytest.mark.parametrize(("method", "suffix"), [("pins", "pins"), ("search", "search")])
@respx.mock
async def test_message_collections_return_typed_pages(method: str, suffix: str) -> None:
    route = respx.get(BASE_PATH.removesuffix("/messages") + f"/{suffix}").mock(
        return_value=httpx.Response(
            200,
            json={"items": [message_payload()], "nextBeforeSeq": "10"},
        )
    )

    async with VoiceRouteClient(token="vrb_secret") as client:
        if method == "pins":
            page = await client.messages.pins("community-id", "channel-id")
        else:
            page = await client.messages.search(
                "community-id", "channel-id", "hello", before_seq="20"
            )

    assert page.items[0].seq == "17"
    assert page.next_before_seq == "10"
    if method == "search":
        assert route.calls[0].request.url.params["beforeSeq"] == "20"
