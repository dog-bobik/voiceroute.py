import httpx
import respx

from voiceroute import VoiceRouteClient


@respx.mock
async def test_list_communities_and_channels() -> None:
    respx.get("https://voiceroute.cc/api/communities").mock(
        return_value=httpx.Response(
            200,
            json={"items": [{"id": "community-id", "name": "Example"}]},
        )
    )
    respx.get("https://voiceroute.cc/api/communities/community-id/channels").mock(
        return_value=httpx.Response(
            200,
            json={"items": [{"id": "channel-id", "name": "general", "type": "text"}]},
        )
    )

    async with VoiceRouteClient(token="vrb_secret") as client:
        communities = await client.communities.list()
        channels = await client.communities.list_channels(communities[0].id)

    assert communities[0].name == "Example"
    assert channels[0].community_id == "community-id"
