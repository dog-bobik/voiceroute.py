"""High-level native application-command declarations and contexts."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from voiceroute.api import InteractionsAPI, MembersAPI
from voiceroute.models import (
    CommandDefinition,
    CommandOption,
    Interaction,
    InteractionResponse,
    Member,
)

InteractionCallback = Callable[["InteractionContext"], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class InteractionContext:
    """A native command invocation with response helpers."""

    interaction: Interaction
    _interactions: InteractionsAPI
    _members: MembersAPI | None = None

    @property
    def options(self) -> dict[str, object]:
        return self.interaction.options

    @property
    def user_id(self) -> int:
        return self.interaction.user.id

    @property
    def community_id(self) -> str:
        return self.interaction.community_id

    @property
    def channel_id(self) -> str:
        return self.interaction.channel_id

    async def respond(self, body: str, *, ephemeral: bool = False) -> InteractionResponse:
        """Complete this interaction with an idempotent response."""
        return await self._interactions.respond(
            self.interaction.id,
            body,
            ephemeral=ephemeral,
        )

    async def fetch_member(self, user_id: int | None = None) -> Member:
        """Fetch the invoking member or another active member in this channel."""
        if self._members is None:
            raise RuntimeError("member API is unavailable in this context")
        member = await self._members.get(
            self.community_id,
            self.user_id if user_id is None else user_id,
            channel_id=self.channel_id,
        )
        if member is None:
            raise LookupError("community member is no longer available")
        return member


@dataclass(frozen=True, slots=True)
class ApplicationCommandHandler:
    """A registered command definition and its async callback."""

    definition: CommandDefinition
    callback: InteractionCallback


class ApplicationCommandRegistry:
    """Store high-level native commands by normalized name."""

    def __init__(self) -> None:
        self._commands: dict[str, ApplicationCommandHandler] = {}

    @property
    def commands(self) -> tuple[ApplicationCommandHandler, ...]:
        return tuple(self._commands.values())

    @property
    def definitions(self) -> tuple[CommandDefinition, ...]:
        return tuple(command.definition for command in self._commands.values())

    def add(self, command: ApplicationCommandHandler) -> None:
        name = command.definition.name.casefold()
        if name in self._commands:
            raise ValueError(f"application command is already registered: {name}")
        self._commands[name] = command

    def get(self, name: str) -> ApplicationCommandHandler | None:
        return self._commands.get(name.casefold())


def application_command(
    *,
    name: str,
    description: str,
    callback: InteractionCallback,
    options: Sequence[CommandOption] = (),
    default_member_permissions: Sequence[str] = (),
) -> ApplicationCommandHandler:
    """Build a validated high-level native command declaration."""
    return ApplicationCommandHandler(
        definition=CommandDefinition(
            name=name,
            description=description,
            options=tuple(options),
            default_member_permissions=tuple(default_member_permissions),
        ),
        callback=callback,
    )
