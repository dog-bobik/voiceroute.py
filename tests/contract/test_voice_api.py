import httpx
import respx

from voiceroute import VoiceRouteClient


@respx.mock
async def test_voice_states_preserve_string_cursor_and_find_member_channel() -> None:
    def response(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("cursor") is None:
            return httpx.Response(
                200,
                json={"items": [], "nextCursor": "9007199254740993"},
            )
        assert request.url.params["cursor"] == "9007199254740993"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "communityId": "community-id",
                        "channelId": "voice-channel-id",
                        "userId": "42",
                        "sessionId": "session-id",
                        "applicationId": None,
                        "status": "CONNECTED",
                    }
                ],
                "nextCursor": None,
            },
        )

    route = respx.get("https://voiceroute.cc/api/v1/communities/community-id/voice-states").mock(
        side_effect=response
    )

    async with VoiceRouteClient(token="vrb_test") as client:
        channel_id = await client.voice.find_member_channel("community-id", 42)

    assert channel_id == "voice-channel-id"
    assert route.call_count == 2
