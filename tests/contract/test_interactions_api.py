from __future__ import annotations

import httpx
import pytest
import respx

from voiceroute import VoiceRouteClient


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
        with pytest.raises(ValueError, match="cannot be empty"):
            await client.interactions.respond("interaction-id", "")
