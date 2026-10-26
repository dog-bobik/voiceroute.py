from __future__ import annotations

import httpx
import pytest
import respx

from voiceroute import VoiceRouteClient

COMMUNITY = "00000000-0000-4000-8000-000000000002"
TIMEOUT = {
    "expiresAt": "2026-10-27T12:00:00.000Z",
    "createdAt": "2026-10-26T12:00:00.000Z",
    "reason": "spam",
    "actorId": 7,
}
BAN = {
    "user": {"id": 42, "username": "user", "displayName": "User"},
    "reason": "spam",
    "createdAt": "2026-10-26T12:00:00.000Z",
    "actorId": 7,
}


@pytest.mark.asyncio
@respx.mock
async def test_ban_and_timeout_member() -> None:
    ban_route = respx.put(f"https://voiceroute.cc/api/communities/{COMMUNITY}/bans/42").mock(
        return_value=httpx.Response(200, json={"ban": BAN})
    )
    timeout_route = respx.put(
        f"https://voiceroute.cc/api/communities/{COMMUNITY}/members/42/timeout"
    ).mock(return_value=httpx.Response(200, json={"timeout": TIMEOUT}))

    async with VoiceRouteClient(token="vrb_test") as client:
        ban = await client.moderation.ban(COMMUNITY, 42, reason="spam")
        timeout = await client.moderation.timeout(COMMUNITY, 42, 3600, reason="spam")

    assert ban.user.id == 42
    assert timeout.actor_id == 7
    assert b'"reason":"spam"' in ban_route.calls.last.request.content
    assert b'"durationSeconds":3600' in timeout_route.calls.last.request.content


@pytest.mark.asyncio
@respx.mock
async def test_read_moderation_snapshot_and_bans() -> None:
    respx.get(f"https://voiceroute.cc/api/communities/{COMMUNITY}/moderation").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "user": BAN["user"],
                        "role": "member",
                        "highestRolePosition": 1,
                        "canBan": True,
                        "canTimeout": True,
                        "timeout": TIMEOUT,
                    }
                ],
                "canBan": True,
                "canTimeout": True,
            },
        )
    )
    respx.get(f"https://voiceroute.cc/api/communities/{COMMUNITY}/bans").mock(
        return_value=httpx.Response(200, json={"items": [BAN]})
    )

    async with VoiceRouteClient(token="vrb_test") as client:
        snapshot = await client.moderation.snapshot(COMMUNITY)
        bans = await client.moderation.bans(COMMUNITY)

    assert snapshot.items[0].can_timeout is True
    assert bans[0].reason == "spam"


@pytest.mark.asyncio
async def test_timeout_and_reason_validation() -> None:
    client = VoiceRouteClient(token="vrb_test")
    with pytest.raises(ValueError, match="duration_seconds"):
        await client.moderation.timeout(COMMUNITY, 42, 0)
    await client.close()
