from __future__ import annotations

import uuid

import httpx
import pytest
import respx

from voiceroute import (
    ActionRow,
    ButtonStyle,
    Component,
    Interaction,
    InteractionMessage,
    VoiceRouteClient,
)


@pytest.mark.asyncio
@respx.mock
async def test_respond_to_interaction_ephemerally() -> None:
    route = respx.post(
        "https://voiceroute.cc/api/bots/@me/interactions/interaction-id/response"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "interaction": {
                    "id": "interaction-id",
                    "status": "completed",
                    "ephemeral": True,
                    "messageSeq": None,
                }
            },
        )
    )
    async with VoiceRouteClient(token="vrb_test") as client:
        response = await client.interactions.respond(
            "interaction-id", "Private pong", ephemeral=True
        )
    assert response.ephemeral is True
    assert response.message_seq is None
    assert b'"ephemeral":true' in route.calls.last.request.content


@pytest.mark.asyncio
async def test_reject_empty_interaction_response() -> None:
    async with VoiceRouteClient(token="vrb_test") as client:
        with pytest.raises(ValueError, match="must contain text or components"):
            await client.interactions.respond("interaction-id", "")


@pytest.mark.asyncio
@respx.mock
async def test_component_only_interaction_response_matches_server_contract() -> None:
    route = respx.post(
        "https://voiceroute.cc/api/v1/interactions/interaction-id/token/callback"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"message": {"id": "message-id", "content": ""}},
        )
    )
    row = ActionRow(
        (Component(type="BUTTON", custom_id="action", style=ButtonStyle.PRIMARY),)
    )

    async with VoiceRouteClient(token="vrb_test") as client:
        await client.interactions.respond(
            "interaction-id",
            "",
            token="token",
            components=(row,),
        )

    assert route.called
    assert route.calls[0].request.read()


def test_message_component_preserves_current_server_payload() -> None:
    interaction = Interaction.from_dict(
        {
            "id": "interaction-id",
            "applicationId": "application-id",
            "communityId": "community-id",
            "channelId": "channel-id",
            "type": "MESSAGE_COMPONENT",
            "token": "interaction-token",
            "user": {"id": "7", "username": "member", "displayName": "Member"},
            "data": {
                "commandId": "command-id",
                "name": "panel",
                "commandVersion": "3",
                "type": "CHAT_INPUT",
                "path": [],
                "options": {},
                "customId": "refresh",
                "componentType": "STRING_SELECT",
                "values": ["one", "two"],
                "resolved": {},
                "messageId": "message-id",
                "messageSeq": "42",
                "sourceVersion": "5",
            },
        }
    )

    assert interaction.type == "MESSAGE_COMPONENT"
    assert interaction.custom_id == "refresh"
    assert interaction.component_type == "STRING_SELECT"
    assert interaction.values == ("one", "two")
    assert interaction.message_id == "message-id"
    assert interaction.message_seq == "42"
    assert interaction.source_version == "5"


@pytest.mark.asyncio
@respx.mock
async def test_v1_callback_and_followup_use_interaction_token() -> None:
    callback = respx.post(
        "https://voiceroute.cc/api/v1/interactions/interaction-id/token/callback"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "id": "message-id",
                    "content": "Ready",
                    "flags": ["EPHEMERAL"],
                    "messageSeq": None,
                    "version": "1",
                }
            },
        )
    )
    followup = respx.post("https://voiceroute.cc/api/v1/webhooks/app-id/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "followup-id",
                "content": "Next",
                "flags": [],
                "messageSeq": "8",
                "version": "1",
            },
        )
    )
    message = InteractionMessage(
        content="Ready",
        flags=("EPHEMERAL",),
        components=(
            ActionRow((Component(type="BUTTON", custom_id="action", style=ButtonStyle.PRIMARY),)),
        ),
    )
    async with VoiceRouteClient(token="vrb_test") as client:
        response = await client.interactions.callback(
            "interaction-id", "token", "MESSAGE", message.to_dict()
        )
        created = await client.interactions.create_followup(
            "app-id", "token", InteractionMessage(content="Next")
        )

    assert response is not None and response.ephemeral
    assert created.message_seq == "8"
    assert b'"type":"MESSAGE"' in callback.calls.last.request.content
    assert b'"content":"Next"' in followup.calls.last.request.content
    assert uuid.UUID(callback.calls.last.request.headers["Idempotency-Key"])
    assert uuid.UUID(followup.calls.last.request.headers["Idempotency-Key"])
