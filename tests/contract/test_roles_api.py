from __future__ import annotations

import httpx
import pytest
import respx

from voiceroute import Permission, PermissionTargetType, VoiceRouteClient

ROLE = {
    "id": "00000000-0000-4000-8000-000000000001",
    "communityId": "00000000-0000-4000-8000-000000000002",
    "name": "Helpers",
    "color": "#64c6b5",
    "position": 3,
    "builtin": None,
    "managedApplicationId": None,
    "permissions": ["viewChannel", "manageMessages"],
    "canManage": True,
}


@pytest.mark.asyncio
@respx.mock
async def test_create_and_edit_role() -> None:
    base = "https://voiceroute.cc/api/communities/00000000-0000-4000-8000-000000000002/roles"
    create = respx.post(base).mock(return_value=httpx.Response(201, json={"role": ROLE}))
    edit = respx.patch(f"{base}/{ROLE['id']}").mock(
        return_value=httpx.Response(200, json={"role": {**ROLE, "name": "Team"}})
    )
    async with VoiceRouteClient(token="vrb_test") as client:
        role = await client.roles.create(
            ROLE["communityId"],
            "Helpers",
            color="#64c6b5",
            permissions=[Permission.VIEW_CHANNEL, Permission.MANAGE_MESSAGES],
        )
        updated = await client.roles.edit(ROLE["communityId"], role.id, name="Team")

    assert role.can_manage is True
    assert updated.name == "Team"
    assert b'"manageMessages"' in create.calls.last.request.content
    assert b'"name":"Team"' in edit.calls.last.request.content


@pytest.mark.asyncio
@respx.mock
async def test_assign_roles_and_set_channel_override() -> None:
    community = ROLE["communityId"]
    role_id = ROLE["id"]
    assign = respx.put(f"https://voiceroute.cc/api/communities/{community}/members/42/roles").mock(
        return_value=httpx.Response(200, json={"roleIds": [role_id]})
    )
    override = respx.put(
        f"https://voiceroute.cc/api/communities/{community}/channels/channel-id/permissions"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "override": {
                    "targetType": "role",
                    "targetId": role_id,
                    "allow": ["sendMessages"],
                    "deny": ["attachFiles"],
                }
            },
        )
    )
    async with VoiceRouteClient(token="vrb_test") as client:
        assigned = await client.roles.set_member_roles(community, 42, [role_id, role_id])
        result = await client.roles.set_channel_override(
            community,
            "channel-id",
            PermissionTargetType.ROLE,
            role_id,
            allow=[Permission.SEND_MESSAGES],
            deny=[Permission.ATTACH_FILES],
        )

    assert assigned == (role_id,)
    assert result.target_type is PermissionTargetType.ROLE
    assert assign.called and override.called
