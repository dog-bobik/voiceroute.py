import httpx
import pytest
import respx

from voiceroute import AutoModConfig, VoiceRouteClient

COMMUNITY = "00000000-0000-4000-8000-000000000002"
CONFIG = {
    "enabled": True,
    "blockedWords": ["spam"],
    "maxMentions": 4,
    "spamLimit": 6,
    "blockDuplicates": True,
    "slowmodeSeconds": 10,
}


@pytest.mark.asyncio
@respx.mock
async def test_get_and_update_automod_config() -> None:
    url = f"https://voiceroute.cc/api/communities/{COMMUNITY}/automod"
    respx.get(url).mock(return_value=httpx.Response(200, json={"config": CONFIG}))
    update = respx.put(url).mock(return_value=httpx.Response(200, json={"config": CONFIG}))

    async with VoiceRouteClient(token="vrb_test") as client:
        current = await client.automod.get(COMMUNITY)
        result = await client.automod.update(COMMUNITY, current)

    assert result.blocked_words == ("spam",)
    assert b'"slowmodeSeconds":10' in update.calls.last.request.content


@pytest.mark.asyncio
async def test_rejects_invalid_automod_config() -> None:
    client = VoiceRouteClient(token="vrb_test")
    with pytest.raises(ValueError, match="max_mentions"):
        await client.automod.update(COMMUNITY, AutoModConfig(max_mentions=101))
    await client.close()
