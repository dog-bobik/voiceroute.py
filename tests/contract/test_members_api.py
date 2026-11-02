from __future__ import annotations

import httpx
import pytest
import respx

from voiceroute import VoiceRouteClient
from voiceroute.models import PresenceStatus

MEMBER = {
    "user": {"id": 42, "username": "alice", "displayName": "Alice", "bot": False},
    "role": "member",
    "joinedAt": "2026-10-26T10:00:00Z",
    "roleIds": ["role-id"],
    "timeoutUntil": None,
    "canBan": True,
    "canTimeout": True,
    "highestRolePosition": 3,
    "roles": [
        {
            "id": "role-id",
            "name": "Helper",
            "color": "#64c6b5",
            "position": 3,
            "builtin": None,
        }
    ],
    "presence": {"id": 42, "status": "available"},
}


@pytest.mark.asyncio
@respx.mock
async def test_list_channel_visible_members() -> None:
    route = respx.get("https://voiceroute.cc/api/communities/community-id/members").mock(
        return_value=httpx.Response(200, json={"items": [MEMBER]})
    )
    async with VoiceRouteClient(token="vrb_test") as client:
        members = await client.members.list("community-id", channel_id="channel-id")

    assert route.calls.last.request.url.params["channelId"] == "channel-id"
    assert members[0].id == 42
    assert members[0].roles[0].name == "Helper"
    assert members[0].presence is not None
    assert members[0].presence.status is PresenceStatus.AVAILABLE


@pytest.mark.asyncio
@respx.mock
async def test_get_member_uses_active_member_snapshot() -> None:
    respx.get("https://voiceroute.cc/api/communities/community-id/members").mock(
        return_value=httpx.Response(200, json={"items": [MEMBER]})
    )
    async with VoiceRouteClient(token="vrb_test", api_version="legacy") as client:
        member = await client.members.get("community-id", 42)

    assert member is not None
    assert member.display_name == "Alice"
    assert member.can_timeout is True


@pytest.mark.asyncio
@respx.mock
async def test_get_member_uses_targeted_v1_route() -> None:
    route = respx.get("https://voiceroute.cc/api/v1/communities/community-id/members/42").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "42",
                "username": "alice",
                "displayName": "Alice",
                "bot": False,
                "role": "member",
            },
        )
    )
    async with VoiceRouteClient(token="vrb_test", api_version="v1") as client:
        member = await client.members.get("community-id", 42)
    assert route.called
    assert member is not None and member.display_name == "Alice"


@pytest.mark.asyncio
@respx.mock
async def test_search_members_preserves_cursor_as_string() -> None:
    route = respx.get("https://voiceroute.cc/api/v1/communities/community-id/members/search").mock(
        return_value=httpx.Response(200, json={"items": [MEMBER], "nextCursor": "9007199254740993"})
    )
    async with VoiceRouteClient(token="vrb_test", api_version="v1") as client:
        page = await client.members.search("community-id", "alice")
    assert route.called
    assert page.items[0].id == 42
    assert page.next_cursor == "9007199254740993"
