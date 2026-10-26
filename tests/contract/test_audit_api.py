import httpx
import pytest
import respx

from voiceroute import VoiceRouteClient

COMMUNITY = "00000000-0000-4000-8000-000000000002"


@pytest.mark.asyncio
@respx.mock
async def test_lists_filtered_audit_entries() -> None:
    route = respx.get(f"https://voiceroute.cc/api/communities/{COMMUNITY}/audit").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "101",
                        "communityId": COMMUNITY,
                        "action": "member.ban",
                        "actionLabel": "Участник заблокирован",
                        "actor": {"id": 7, "username": "mod", "displayName": "Mod"},
                        "target": {"type": "member", "id": "42", "label": "User"},
                        "reason": "spam",
                        "before": {"active": True},
                        "after": {"active": False},
                        "createdAt": "2026-10-26T12:00:00.000Z",
                    }
                ],
                "nextBefore": "101",
                "actors": [{"id": 7, "username": "mod", "displayName": "Mod"}],
                "actions": [{"id": "member.ban", "label": "Участник заблокирован"}],
                "retentionDays": 45,
            },
        )
    )

    async with VoiceRouteClient(token="vrb_test") as client:
        page = await client.audit.list(
            COMMUNITY, before="150", action="member.ban", actor_id=7, limit=25
        )

    assert page.items[0].target.id == "42"
    assert page.next_before == "101"
    assert page.retention_days == 45
    assert route.calls.last.request.url.params["before"] == "150"
    assert route.calls.last.request.url.params["limit"] == "25"


@pytest.mark.asyncio
async def test_rejects_invalid_audit_filters() -> None:
    client = VoiceRouteClient(token="vrb_test")
    with pytest.raises(ValueError, match="limit"):
        await client.audit.list(COMMUNITY, limit=101)
    await client.close()
