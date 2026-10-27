"""Complete Bot Platform v1 application-command registry."""

from __future__ import annotations

import builtins
from collections.abc import Sequence
from dataclasses import dataclass

from voiceroute.models import (
    ApplicationCommand,
    CommandDefinition,
    CommandPermissions,
    CommandPermissionTarget,
)
from voiceroute.transport import HTTPTransport


@dataclass(frozen=True, slots=True)
class CommandSyncDiff:
    create: tuple[str, ...]
    update: tuple[str, ...]
    delete: tuple[str, ...]
    unchanged: tuple[str, ...]


class ApplicationCommandsAPI:
    """Global/community CRUD, atomic sync, dry diff, and permission rules."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    @staticmethod
    def _base(application_id: str, community_id: str | None = None) -> str:
        root = f"/api/v1/applications/{application_id}"
        return (
            f"{root}/communities/{community_id}/commands"
            if community_id is not None
            else f"{root}/commands"
        )

    async def list(
        self, application_id: str, *, community_id: str | None = None
    ) -> builtins.list[ApplicationCommand]:
        payload = await self._transport.request("GET", self._base(application_id, community_id))
        return [ApplicationCommand.from_dict(item) for item in (payload or {}).get("items", [])]

    async def get(
        self, application_id: str, command_id: str, *, community_id: str | None = None
    ) -> ApplicationCommand:
        payload = await self._transport.request(
            "GET", f"{self._base(application_id, community_id)}/{command_id}"
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no application command")
        return ApplicationCommand.from_dict(payload)

    async def create(
        self,
        application_id: str,
        command: CommandDefinition,
        *,
        community_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ApplicationCommand:
        payload = await self._transport.request(
            "POST",
            self._base(application_id, community_id),
            json=command.to_dict(),
            idempotency_key=idempotency_key,
            generate_idempotency_key=idempotency_key is None,
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no created application command")
        return ApplicationCommand.from_dict(payload)

    async def update(
        self,
        application_id: str,
        command_id: str,
        command: CommandDefinition,
        *,
        version: str,
        community_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ApplicationCommand:
        payload = await self._transport.request(
            "PATCH",
            f"{self._base(application_id, community_id)}/{command_id}",
            json=command.to_dict(),
            if_match=version,
            idempotency_key=idempotency_key,
            generate_idempotency_key=idempotency_key is None,
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no updated application command")
        return ApplicationCommand.from_dict(payload)

    async def delete(
        self,
        application_id: str,
        command_id: str,
        *,
        version: str,
        community_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        await self._transport.request(
            "DELETE",
            f"{self._base(application_id, community_id)}/{command_id}",
            if_match=version,
            idempotency_key=idempotency_key,
            generate_idempotency_key=idempotency_key is None,
        )

    async def sync(
        self,
        application_id: str,
        commands: Sequence[CommandDefinition],
        *,
        community_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> builtins.list[ApplicationCommand]:
        payload = await self._transport.request(
            "PUT",
            self._base(application_id, community_id),
            json={"commands": [command.to_dict() for command in commands]},
            idempotency_key=idempotency_key,
            generate_idempotency_key=idempotency_key is None,
        )
        return [ApplicationCommand.from_dict(item) for item in (payload or {}).get("items", [])]

    replace = sync

    async def diff(
        self,
        application_id: str,
        commands: Sequence[CommandDefinition],
        *,
        community_id: str | None = None,
    ) -> CommandSyncDiff:
        current = await self.list(application_id, community_id=community_id)
        remote = {item.name.casefold(): item for item in current}
        desired = {item.name.casefold(): item for item in commands}
        create = tuple(sorted(set(desired) - set(remote)))
        delete = tuple(sorted(set(remote) - set(desired)))
        update = tuple(
            sorted(
                name
                for name in set(remote) & set(desired)
                if desired[name].to_dict() != _definition_dict(remote[name])
            )
        )
        unchanged = tuple(sorted((set(remote) & set(desired)) - set(update)))
        return CommandSyncDiff(create, update, delete, unchanged)

    async def get_permissions(
        self, application_id: str, community_id: str, command_id: str
    ) -> CommandPermissions:
        payload = await self._transport.request(
            "GET",
            f"/api/v1/applications/{application_id}/communities/{community_id}"
            f"/commands/{command_id}/permissions",
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no command permissions")
        return CommandPermissions.from_dict(payload)

    async def list_permissions(
        self, application_id: str, community_id: str
    ) -> builtins.list[CommandPermissions]:
        payload = await self._transport.request(
            "GET",
            f"/api/v1/applications/{application_id}/communities/{community_id}/command-permissions",
        )
        return [CommandPermissions.from_dict(item) for item in (payload or {}).get("items", [])]

    async def discover_channel(
        self, community_id: str, channel_id: str
    ) -> builtins.list[ApplicationCommand]:
        payload = await self._transport.request(
            "GET",
            f"/api/v1/communities/{community_id}/channels/{channel_id}/application-commands",
        )
        return [ApplicationCommand.from_dict(item) for item in (payload or {}).get("items", [])]

    async def discover_community(self, community_id: str) -> builtins.list[ApplicationCommand]:
        payload = await self._transport.request(
            "GET", f"/api/v1/communities/{community_id}/application-commands"
        )
        return [ApplicationCommand.from_dict(item) for item in (payload or {}).get("items", [])]

    async def replace_permissions(
        self,
        application_id: str,
        community_id: str,
        command_id: str,
        targets: Sequence[CommandPermissionTarget],
        *,
        version: str,
        idempotency_key: str | None = None,
    ) -> CommandPermissions:
        payload = await self._transport.request(
            "PUT",
            f"/api/v1/applications/{application_id}/communities/{community_id}"
            f"/commands/{command_id}/permissions",
            json={"targets": [target.to_dict() for target in targets]},
            if_match=version,
            idempotency_key=idempotency_key,
            generate_idempotency_key=idempotency_key is None,
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no command permissions")
        return CommandPermissions.from_dict(payload)


def _definition_dict(command: ApplicationCommand) -> dict[str, object]:
    return CommandDefinition(
        name=command.name,
        description=command.description,
        type=command.type,
        options=command.options,
        contexts=command.contexts,
        default_member_permissions=command.default_member_permissions,
    ).to_dict()
