"""High-level native application-command declarations and contexts."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field

from voiceroute.api import InteractionsAPI, MembersAPI
from voiceroute.errors import Conflict
from voiceroute.models import (
    ActionRow,
    CommandChoice,
    CommandContext,
    CommandDefinition,
    CommandOption,
    CommandType,
    Interaction,
    InteractionMessage,
    InteractionResponse,
    Member,
    Modal,
)

InteractionCallback = Callable[["InteractionContext"], Awaitable[None]]


@dataclass(slots=True)
class InteractionContext:
    """A native command invocation with response helpers."""

    interaction: Interaction
    _interactions: InteractionsAPI
    _members: MembersAPI | None = None
    _received_at: float = field(default_factory=time.monotonic, repr=False)
    _initial_response_sent: bool = field(default=False, init=False, repr=False)

    @property
    def options(self) -> dict[str, object]:
        return self.interaction.options

    @property
    def user_id(self) -> int:
        return self.interaction.user.id

    @property
    def community_id(self) -> str:
        if self.interaction.community_id is None:
            raise RuntimeError("interaction does not belong to a community")
        return self.interaction.community_id

    @property
    def channel_id(self) -> str:
        return self.interaction.channel_id

    def _token(self) -> str:
        if self.interaction.token is None:
            raise RuntimeError("v1 interaction token is unavailable")
        return self.interaction.token

    def _claim_initial_response(self) -> None:
        if self._initial_response_sent:
            raise RuntimeError("interaction already has an initial response")
        if time.monotonic() - self._received_at > 3.0:
            raise TimeoutError("interaction initial response deadline exceeded")
        self._initial_response_sent = True

    async def respond(
        self,
        body: str,
        *,
        ephemeral: bool | None = None,
        components: Sequence[ActionRow] = (),
    ) -> InteractionResponse:
        """Complete this interaction with an idempotent response."""
        self._claim_initial_response()
        private = (self.interaction.context != "COMMUNITY") if ephemeral is None else ephemeral
        if self.interaction.token is None:
            return await self._interactions.respond(
                self.interaction.id,
                body,
                ephemeral=private,
            )
        return await self._interactions.respond(
            self.interaction.id,
            body,
            ephemeral=private,
            token=self.interaction.token,
            components=tuple(components),
        )

    send_message = respond

    async def defer(self, *, ephemeral: bool | None = None) -> None:
        self._claim_initial_response()
        private = self.interaction.context != "COMMUNITY" if ephemeral is None else ephemeral
        try:
            await self._interactions.defer(self.interaction.id, self._token(), ephemeral=private)
        except Conflict as error:
            if error.code != "INTERACTION_ALREADY_ACKNOWLEDGED":
                raise

    async def autocomplete(self, choices: Sequence[CommandChoice]) -> None:
        self._claim_initial_response()
        await self._interactions.autocomplete(self.interaction.id, self._token(), tuple(choices))

    async def show_modal(self, modal: Modal) -> None:
        self._claim_initial_response()
        await self._interactions.show_modal(self.interaction.id, self._token(), modal)

    async def update_message(
        self,
        body: str,
        *,
        components: Sequence[ActionRow] = (),
    ) -> InteractionResponse | None:
        """Acknowledge a component interaction by updating its source message."""
        if self.interaction.type != "MESSAGE_COMPONENT":
            raise RuntimeError("only a message component can update its source message")
        self._claim_initial_response()
        return await self._interactions.update_message(
            self.interaction.id,
            self._token(),
            InteractionMessage(content=body, components=tuple(components)),
        )

    async def defer_update(self) -> None:
        """Acknowledge a component interaction without changing its source yet."""
        if self.interaction.type != "MESSAGE_COMPONENT":
            raise RuntimeError("only a message component can defer a source update")
        self._claim_initial_response()
        await self._interactions.defer_update(self.interaction.id, self._token())

    async def edit_original(
        self,
        body: str,
        *,
        message_id: str = "@original",
        components: Sequence[ActionRow] = (),
    ) -> InteractionResponse:
        return await self._interactions.edit_response(
            self.interaction.application_id,
            self._token(),
            message_id,
            InteractionMessage(content=body, components=tuple(components)),
        )

    async def delete_original(self, *, message_id: str = "@original") -> None:
        await self._interactions.delete_response(
            self.interaction.application_id, self._token(), message_id
        )

    async def followup(self, body: str, *, ephemeral: bool | None = None) -> InteractionResponse:
        private = self.interaction.context != "COMMUNITY" if ephemeral is None else ephemeral
        return await self._interactions.create_followup(
            self.interaction.application_id,
            self._token(),
            InteractionMessage(
                content=body,
                flags=("EPHEMERAL",) if private else (),
            ),
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
    community_id: str | None = None


class ApplicationCommandRegistry:
    """Store high-level native commands by normalized name."""

    def __init__(self) -> None:
        self._commands: dict[tuple[str | None, str], ApplicationCommandHandler] = {}

    @property
    def commands(self) -> tuple[ApplicationCommandHandler, ...]:
        return tuple(self._commands.values())

    @property
    def definitions(self) -> tuple[CommandDefinition, ...]:
        return tuple(command.definition for command in self._commands.values())

    def add(self, command: ApplicationCommandHandler) -> None:
        name = command.definition.name.casefold()
        key = (command.community_id, name)
        if key in self._commands:
            raise ValueError(f"application command is already registered: {name}")
        self._commands[key] = command

    def get(self, name: str, community_id: str | None = None) -> ApplicationCommandHandler | None:
        normalized = name.casefold()
        return self._commands.get((community_id, normalized)) or self._commands.get(
            (None, normalized)
        )

    def definitions_for(self, community_id: str | None) -> tuple[CommandDefinition, ...]:
        return tuple(
            command.definition
            for command in self._commands.values()
            if command.community_id == community_id
        )

    @property
    def community_ids(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                command.community_id
                for command in self._commands.values()
                if command.community_id is not None
            )
        )


def application_command(
    *,
    name: str,
    description: str,
    callback: InteractionCallback,
    type: CommandType = CommandType.CHAT_INPUT,
    options: Sequence[CommandOption] = (),
    contexts: Sequence[CommandContext] = (CommandContext.COMMUNITY,),
    default_member_permissions: Sequence[str] = (),
    community_id: str | None = None,
) -> ApplicationCommandHandler:
    """Build a validated high-level native command declaration."""
    return ApplicationCommandHandler(
        definition=CommandDefinition(
            name=name,
            description=description,
            type=type,
            options=tuple(options),
            contexts=tuple(contexts),
            default_member_permissions=tuple(default_member_permissions),
        ),
        callback=callback,
        community_id=community_id,
    )
