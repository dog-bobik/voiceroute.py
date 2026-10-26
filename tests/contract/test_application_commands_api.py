from __future__ import annotations

import httpx
import pytest
import respx

from voiceroute import VoiceRouteClient
from voiceroute.models import CommandDefinition, CommandOption, CommandOptionType

COMMAND = {
    "id": "00000000-0000-4000-8000-000000000001",
    "applicationId": "00000000-0000-4000-8000-000000000002",
    "version": 2,
    "name": "echo",
    "description": "Repeat text",
    "options": [
        {
            "name": "text",
            "description": "Text",
            "type": "string",
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
        "https://voiceroute.cc/api/applications/00000000-0000-4000-8000-000000000002/commands"
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
        "https://voiceroute.cc/api/applications/00000000-0000-4000-8000-000000000002/commands"
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
    assert commands[0].version == 2
    assert route.calls.last.request.headers["Authorization"] == "Bot vrb_test"
    assert b'"maxLength":1000' in route.calls.last.request.content
