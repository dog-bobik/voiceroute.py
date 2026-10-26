"""Application-command registry endpoints."""

import builtins
from collections.abc import Sequence

from voiceroute.models import ApplicationCommand, CommandDefinition
from voiceroute.transport import HTTPTransport


class ApplicationCommandsAPI:
    """Read and atomically replace one application's native commands."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def list(self, application_id: str) -> builtins.list[ApplicationCommand]:
        payload = await self._transport.request(
            "GET", f"/api/applications/{application_id}/commands"
        )
        if payload is None:
            return []
        return [ApplicationCommand.from_dict(item) for item in payload.get("items", [])]

    async def replace(
        self,
        application_id: str,
        commands: Sequence[CommandDefinition],
    ) -> builtins.list[ApplicationCommand]:
        """Replace the complete command registry for an application."""
        payload = await self._transport.request(
            "PUT",
            f"/api/applications/{application_id}/commands",
            json={"commands": [command.to_dict() for command in commands]},
        )
        if payload is None:
            return []
        return [ApplicationCommand.from_dict(item) for item in payload.get("items", [])]
