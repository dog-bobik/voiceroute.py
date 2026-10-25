"""High-level event-driven bot runtime."""

from __future__ import annotations

import asyncio
import inspect
import shlex
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from voiceroute.client import VoiceRouteClient
from voiceroute.commands.context import Context
from voiceroute.errors import NoChannelsAvailable
from voiceroute.events import AccessLost, MessageUpserted
from voiceroute.models import BotIdentity, Channel, Message

AsyncHandler = Callable[..., Awaitable[None]]
HandlerT = TypeVar("HandlerT", bound=AsyncHandler)


@dataclass(frozen=True, slots=True)
class ChannelTarget:
    """A community channel selected for event consumption."""

    community_id: str
    channel_id: str


class Bot:
    """Run commands and event handlers for one VoiceRoute text channel."""

    def __init__(
        self,
        *,
        token: str,
        community_id: str | None = None,
        channel_id: str | None = None,
        command_prefix: str = "!",
        base_url: str = "https://voiceroute.cc",
        max_event_streams: int = 32,
    ) -> None:
        if not command_prefix:
            raise ValueError("command_prefix cannot be empty")
        if channel_id is not None and community_id is None:
            raise ValueError("community_id is required when channel_id is provided")
        if not 1 <= max_event_streams <= 32:
            raise ValueError("max_event_streams must be between 1 and 32")
        self.client = VoiceRouteClient(token=token, base_url=base_url)
        self.community_id = community_id
        self.channel_id = channel_id
        self.command_prefix = command_prefix
        self.max_event_streams = max_event_streams
        self.user: BotIdentity | None = None
        self.listening_channels: tuple[ChannelTarget, ...] = ()
        self._commands: dict[str, AsyncHandler] = {}
        self._events: dict[str, AsyncHandler] = {}
        self._closed = False

    def command(self, name: str | None = None) -> Callable[[HandlerT], HandlerT]:
        """Register an async prefix-command handler."""

        def decorator(handler: HandlerT) -> HandlerT:
            command_name = (name or handler.__name__).casefold()
            if not command_name or any(character.isspace() for character in command_name):
                raise ValueError("command name must be one non-empty word")
            self._ensure_async(handler)
            if command_name in self._commands:
                raise ValueError(f"command is already registered: {command_name}")
            self._commands[command_name] = handler
            return handler

        return decorator

    def event(self, handler: HandlerT) -> HandlerT:
        """Register an async handler named on_ready, on_message, on_access_lost, or on_error."""
        self._ensure_async(handler)
        self._events[handler.__name__] = handler
        return handler

    async def start(self) -> None:
        """Authenticate and process channel events until stopped or access is lost."""
        self.user = await self.client.bots.get_current()
        self.listening_channels = tuple(await self._discover_channels())
        await self._dispatch("on_ready")

        try:
            async with asyncio.TaskGroup() as tasks:
                for target in self.listening_channels:
                    tasks.create_task(
                        self._consume_channel(target),
                        name=f"voiceroute:{target.community_id}:{target.channel_id}",
                    )
        finally:
            await self.close()

    def run(self) -> None:
        """Run the bot in a new asyncio event loop."""
        asyncio.run(self.start())

    async def close(self) -> None:
        """Stop the runtime and release its HTTP connections."""
        if not self._closed:
            self._closed = True
            await self.client.close()

    async def _handle_message(self, event: MessageUpserted) -> None:
        message = event.message
        await self._dispatch("on_message", message)
        if not self._can_invoke_command(message):
            return

        try:
            parts = shlex.split(message.body[len(self.command_prefix) :])
        except ValueError as exc:
            await self._dispatch_error(exc)
            return
        if not parts:
            return

        command_name = parts[0].casefold()
        handler = self._commands.get(command_name)
        if handler is None:
            return
        context = Context(
            message=message,
            command=command_name,
            args=tuple(parts[1:]),
            _messages=self.client.messages,
        )
        try:
            await handler(context)
        except Exception as exc:
            await self._dispatch_error(exc)

    async def _consume_channel(self, target: ChannelTarget) -> None:
        async for event in self.client.events.listen_messages(
            target.community_id,
            target.channel_id,
        ):
            if self._closed:
                return
            if isinstance(event, AccessLost):
                await self._dispatch("on_access_lost", event, target)
                return
            await self._handle_message(event)

    async def _discover_channels(self) -> list[ChannelTarget]:
        if self.community_id is not None and self.channel_id is not None:
            return [ChannelTarget(self.community_id, self.channel_id)]

        if self.community_id is not None:
            community_ids = [self.community_id]
        else:
            community_ids = [community.id for community in await self.client.communities.list()]

        targets: list[ChannelTarget] = []
        for community_id in community_ids:
            channels = await self.client.communities.list_channels(community_id)
            targets.extend(
                ChannelTarget(community_id, channel.id)
                for channel in channels
                if self._is_text_channel(channel)
            )

        if not targets:
            raise NoChannelsAvailable(
                "the bot is not installed in a community with an accessible text channel"
            )
        if len(targets) > self.max_event_streams:
            raise NoChannelsAvailable(
                f"discovered {len(targets)} text channels, but max_event_streams is "
                f"{self.max_event_streams}; provide community_id/channel_id or narrow "
                "the installation"
            )
        return targets

    @staticmethod
    def _is_text_channel(channel: Channel) -> bool:
        return channel.kind.casefold() == "text"

    def _can_invoke_command(self, message: Message) -> bool:
        if message.deleted or message.edited_at is not None or message.webhook:
            return False
        if message.author is None or message.author.bot:
            return False
        if self.user is not None and message.author.id == self.user.user.id:
            return False
        return message.body.startswith(self.command_prefix)

    async def _dispatch(self, event_name: str, *args: Any) -> None:
        handler = self._events.get(event_name)
        if handler is None:
            return
        try:
            await handler(*args)
        except Exception as exc:
            if event_name == "on_error":
                raise
            await self._dispatch_error(exc)

    async def _dispatch_error(self, error: Exception) -> None:
        handler = self._events.get("on_error")
        if handler is None:
            raise error
        await handler(error)

    @staticmethod
    def _ensure_async(handler: AsyncHandler) -> None:
        if not inspect.iscoroutinefunction(handler):
            raise TypeError("bot handlers must be async functions")
