from __future__ import annotations

import httpx
import pytest
import respx

from voiceroute import VoiceRouteClient
from voiceroute.models import (
    CommandDefinition,
    CommandOption,
    CommandOptionType,
    CommandPermissionTarget,
)

COMMAND = {
    "id": "00000000-0000-4000-8000-000000000001",
    "applicationId": "00000000-0000-4000-8000-000000000002",
    "version": "2",
    "type": "CHAT_INPUT",
    "scope": {"type": "global"},
    "contexts": ["COMMUNITY"],
    "nameLocalizations": {},
    "descriptionLocalizations": {},
    "nsfw": False,
    "name": "echo",
    "description": "Repeat text",
    "options": [
        {
            "name": "text",
            "description": "Text",
            "type": "STRING",
            "required": True,
            "maxLength": 1000,
        }
    ],
    "defaultMemberPermissions": [],
}


@pytest.mark.asyncio
@respx.mock
async def test_list_application_commands() -> None:
    route = respx.get(
        "https://voiceroute.cc/api/v1/applications/00000000-0000-4000-8000-000000000002/commands"
    ).mock(return_value=httpx.Response(200, json={"items": [COMMAND]}))
    async with VoiceRouteClient(token="vrb_test") as client:
        commands = await client.application_commands.list(COMMAND["applicationId"])
    assert route.called
    assert commands[0].name == "echo"
    assert commands[0].options[0].max_length == 1000


@pytest.mark.asyncio
@respx.mock
async def test_replace_application_commands_sends_complete_registry() -> None:
    route = respx.put(
        "https://voiceroute.cc/api/v1/applications/00000000-0000-4000-8000-000000000002/commands"
    ).mock(return_value=httpx.Response(200, json={"items": [COMMAND]}))
    definition = CommandDefinition(
        name="echo",
        description="Repeat text",
        options=(
            CommandOption(
                name="text",
                description="Text",
                type=CommandOptionType.STRING,
                required=True,
                max_length=1000,
            ),
        ),
    )
    async with VoiceRouteClient(token="vrb_test") as client:
        commands = await client.application_commands.replace(COMMAND["applicationId"], [definition])
    assert commands[0].version == "2"
    assert route.calls.last.request.headers["Authorization"] == "Bot vrb_test"
    assert b'"maxLength":1000' in route.calls.last.request.content
    assert route.calls.last.request.headers["Idempotency-Key"]


@pytest.mark.asyncio
@respx.mock
async def test_community_crud_and_permission_replacement_use_versions() -> None:
    base = (
        "https://voiceroute.cc/api/v1/applications/"
        "00000000-0000-4000-8000-000000000002/communities/community/commands"
    )
    create = respx.post(base).mock(return_value=httpx.Response(201, json=COMMAND))
    update = respx.patch(f"{base}/{COMMAND['id']}").mock(
        return_value=httpx.Response(200, json={**COMMAND, "version": "3"})
    )
    permissions = respx.put(f"{base}/{COMMAND['id']}/permissions").mock(
        return_value=httpx.Response(
            200,
            json={
                "commandId": COMMAND["id"],
                "communityId": "community",
                "version": "4",
                "targets": [{"type": "allMembers", "allow": True}],
            },
        )
    )
    definition = CommandDefinition(name="echo", description="Repeat text")
    async with VoiceRouteClient(token="vrb_test") as client:
        created = await client.application_commands.create(
            COMMAND["applicationId"], definition, community_id="community"
        )
        changed = await client.application_commands.update(
            COMMAND["applicationId"],
            COMMAND["id"],
            definition,
            community_id="community",
            version=created.version,
        )
        rules = await client.application_commands.replace_permissions(
            COMMAND["applicationId"],
            "community",
            COMMAND["id"],
            [CommandPermissionTarget("allMembers", True)],
            version=changed.version,
        )

    assert create.calls.last.request.headers["Idempotency-Key"]
    assert update.calls.last.request.headers["If-Match"] == "2"
    assert permissions.calls.last.request.headers["If-Match"] == "3"
    assert rules.targets[0].allow
