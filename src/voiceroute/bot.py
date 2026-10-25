"""High-level event-driven bot runtime."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import Any, TypeVar, cast

from voiceroute.client import VoiceRouteClient
from voiceroute.commands import (
    Command,
    CommandPipeline,
    CommandRegistry,
    Context,
    Middleware,
    PrefixCommandAdapter,
)
from voiceroute.errors import (
    BotAlreadyRunning,
    BotClosed,
    CommandError,
    CommandNotFound,
    ExtensionAlreadyLoaded,
    ExtensionNotLoaded,
    ExtensionSetupError,
    NoChannelsAvailable,
)
from voiceroute.events import (
    AccessLost,
    CursorStore,
    EventTransport,
    LegacySSETransport,
    MemoryCursorStore,
    MessageUpserted,
)
from voiceroute.events.transport import ChannelTarget
from voiceroute.extensions import Extension, extension_command, listener_name
from voiceroute.models import BotIdentity, Channel, Message
from voiceroute.runtime import RuntimeState

AsyncHandler = Callable[..., Awaitable[None]]
HandlerT = TypeVar("HandlerT", bound=AsyncHandler)
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExtensionRegistration:
    """Handlers installed by one extension instance."""

    extension: Extension
    commands: tuple[Command, ...]
    listeners: tuple[tuple[str, AsyncHandler], ...]
    module_name: str | None = None


class Bot:
    """Run commands and event handlers for one VoiceRoute text channel."""

    def __init__(
        self,
        *,
        token: str,
        community_id: str | None = None,
        channel_id: str | None = None,
        command_prefix: str | Sequence[str] = ("/", "!"),
        base_url: str = "https://voiceroute.cc",
        max_event_streams: int = 32,
        initial_after_seq: str | None = "0",
        cursor_store: CursorStore | None = None,
        event_transport: EventTransport | None = None,
        max_consumer_backoff: float = 30.0,
    ) -> None:
        prefixes = (command_prefix,) if isinstance(command_prefix, str) else tuple(command_prefix)
        self.command_adapter = PrefixCommandAdapter(prefixes)
        if channel_id is not None and community_id is None:
            raise ValueError("community_id is required when channel_id is provided")
        if not 1 <= max_event_streams <= 32:
            raise ValueError("max_event_streams must be between 1 and 32")
        if max_consumer_backoff <= 0:
            raise ValueError("max_consumer_backoff must be positive")
        self.client = VoiceRouteClient(token=token, base_url=base_url)
        self.community_id = community_id
        self.channel_id = channel_id
        self.command_prefixes = self.command_adapter.prefixes
        self.max_event_streams = max_event_streams
        self.max_consumer_backoff = max_consumer_backoff
        self.initial_after_seq = initial_after_seq
        self.cursor_store = cursor_store or MemoryCursorStore()
        self.base_url = base_url.rstrip("/")
        self.event_transport = event_transport or LegacySSETransport(
            self.client.events,
            self.client.messages,
            base_url=self.base_url,
        )
        self.user: BotIdentity | None = None
        self.listening_channels: tuple[ChannelTarget, ...] = ()
        self.command_registry = CommandRegistry()
        self.command_pipeline = CommandPipeline()
        self._events: dict[str, list[AsyncHandler]] = {}
        self._extensions: dict[str, ExtensionRegistration] = {}
        self._extension_modules: dict[str, str] = {}
        self._consumer_tasks: set[asyncio.Task[None]] = set()
        self._ready = asyncio.Event()
        self._stop_lock = asyncio.Lock()
        self.state = RuntimeState.CREATED
        self._closed = False

    def command(
        self,
        name: str | None = None,
        *,
        aliases: Sequence[str] = (),
        description: str | None = None,
        usage: str | None = None,
    ) -> Callable[[HandlerT], HandlerT]:
        """Register an async command with transport-independent metadata."""

        def decorator(handler: HandlerT) -> HandlerT:
            self._ensure_async(handler)
            self.command_registry.add(
                Command.from_callback(
                    handler,
                    name=name,
                    aliases=aliases,
                    description=description,
                    usage=usage,
                )
            )
            return handler

        return decorator

    @property
    def commands(self) -> tuple[Command, ...]:
        """Return commands in registration order without aliases."""
        return self.command_registry.commands

    def get_command(self, name: str) -> Command | None:
        """Find a command by canonical name or alias."""
        return self.command_registry.get(name)

    def middleware(self, handler: Middleware) -> Middleware:
        """Register global command middleware in declaration order."""
        self.command_pipeline.add_middleware(handler)
        return handler

    def event(self, handler: HandlerT) -> HandlerT:
        """Register an async handler named on_ready, on_message, on_access_lost, or on_error."""
        self._ensure_async(handler)
        self.add_listener(handler, handler.__name__)
        return handler

    def add_listener(self, handler: AsyncHandler, name: str | None = None) -> None:
        """Register an async event listener."""
        self._ensure_async(handler)
        self._events.setdefault(name or handler.__name__, []).append(handler)

    def remove_listener(self, handler: AsyncHandler, name: str | None = None) -> None:
        """Remove one exact event listener."""
        event_name = name or handler.__name__
        handlers = self._events.get(event_name)
        if handlers is None or handler not in handlers:
            raise ValueError(f"listener is not registered: {event_name}")
        handlers.remove(handler)
        if not handlers:
            del self._events[event_name]

    @property
    def extensions(self) -> tuple[Extension, ...]:
        """Return active extension instances."""
        return tuple(registration.extension for registration in self._extensions.values())

    async def add_extension(
        self,
        extension: Extension,
        *,
        module_name: str | None = None,
    ) -> None:
        """Atomically initialize and register an extension instance."""
        name = extension.qualified_name
        if name in self._extensions:
            raise ExtensionAlreadyLoaded(name)

        commands: list[Command] = []
        listeners: list[tuple[str, AsyncHandler]] = []
        await extension.setup(self)
        try:
            for _, member in inspect.getmembers(extension, predicate=callable):
                bound_handler = cast(AsyncHandler, member)
                metadata = extension_command(member)
                if metadata is not None:
                    self._ensure_async(bound_handler)
                    command = Command.from_callback(
                        bound_handler,
                        name=metadata.name,
                        aliases=metadata.aliases,
                        description=metadata.description,
                        usage=metadata.usage,
                    )
                    self.command_registry.add(command)
                    commands.append(command)
                event_name = listener_name(member)
                if event_name is not None:
                    self.add_listener(bound_handler, event_name)
                    listeners.append((event_name, bound_handler))
        except Exception:
            for command in reversed(commands):
                self.command_registry.remove(command)
            for event_name, handler in reversed(listeners):
                self.remove_listener(handler, event_name)
            await extension.teardown(self)
            raise

        self._extensions[name] = ExtensionRegistration(
            extension=extension,
            commands=tuple(commands),
            listeners=tuple(listeners),
            module_name=module_name,
        )
        if module_name is not None:
            self._extension_modules[module_name] = name

    async def remove_extension(self, name: str) -> Extension:
        """Unregister an extension and release its resources."""
        registration = self._extensions.pop(name, None)
        if registration is None:
            raise ExtensionNotLoaded(name)
        for command in registration.commands:
            self.command_registry.remove(command)
        for event_name, handler in registration.listeners:
            self.remove_listener(handler, event_name)
        if registration.module_name is not None:
            self._extension_modules.pop(registration.module_name, None)
        await registration.extension.teardown(self)
        return registration.extension

    async def load_extension(self, module_name: str) -> Extension:
        """Import a module whose async setup returns an Extension instance."""
        if module_name in self._extension_modules:
            raise ExtensionAlreadyLoaded(module_name)
        module = importlib.import_module(module_name)
        extension = await self._setup_extension_module(module)
        await self.add_extension(extension, module_name=module_name)
        return extension

    async def unload_extension(self, module_name: str) -> Extension:
        """Unload an extension previously loaded from a module."""
        name = self._extension_modules.get(module_name)
        if name is None:
            raise ExtensionNotLoaded(module_name)
        return await self.remove_extension(name)

    async def reload_extension(self, module_name: str) -> Extension:
        """Reload a module, restoring its previous instance if setup fails."""
        name = self._extension_modules.get(module_name)
        if name is None:
            raise ExtensionNotLoaded(module_name)
        previous = self._extensions[name]
        module = importlib.import_module(module_name)
        await self.remove_extension(name)
        try:
            reloaded = importlib.reload(module)
            extension = await self._setup_extension_module(reloaded)
            await self.add_extension(extension, module_name=module_name)
        except Exception:
            await self.add_extension(previous.extension, module_name=module_name)
            raise
        return extension

    async def _setup_extension_module(self, module: ModuleType) -> Extension:
        setup = getattr(module, "setup", None)
        if setup is None or not inspect.iscoroutinefunction(setup):
            raise ExtensionSetupError(
                f"extension module {module.__name__!r} must define async setup(bot)"
            )
        extension = await setup(self)
        if not isinstance(extension, Extension):
            raise ExtensionSetupError(
                f"extension module {module.__name__!r} setup must return Extension"
            )
        return extension

    async def start(self) -> None:
        """Initialize the runtime and process events until every consumer stops."""
        if self.state in (RuntimeState.STARTING, RuntimeState.RUNNING, RuntimeState.STOPPING):
            raise BotAlreadyRunning("bot is already starting or running")
        if self.state is RuntimeState.CLOSED:
            raise BotClosed("a closed bot instance cannot be started again")
        self.state = RuntimeState.STARTING
        try:
            await self.setup_hook()
            self.user = await self.client.bots.get_current()
            self.listening_channels = tuple(await self._discover_channels())
            await self._dispatch("on_connect")
            self.state = RuntimeState.RUNNING
            self._ready.set()
            await self._dispatch("on_ready")

            self._consumer_tasks = {
                asyncio.create_task(
                    self._supervise_channel(target),
                    name=f"voiceroute:{target.community_id}:{target.channel_id}",
                )
                for target in self.listening_channels
            }
            await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
        finally:
            await self.stop()

    async def setup_hook(self) -> None:
        """Override to initialize application resources before authentication."""

    def run(self) -> None:
        """Run the bot in a new asyncio event loop."""
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            pass

    async def stop(self) -> None:
        """Idempotently stop consumers, extensions, hooks, and network resources."""
        async with self._stop_lock:
            if self.state is RuntimeState.CLOSED:
                return
            self.state = RuntimeState.STOPPING
            self._closed = True
            self._ready.clear()

            current = asyncio.current_task()
            tasks = tuple(task for task in self._consumer_tasks if task is not current)
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self._consumer_tasks.clear()

            try:
                await self._dispatch("on_shutdown")
            finally:
                for name in tuple(reversed(self._extensions)):
                    try:
                        await self.remove_extension(name)
                    except Exception:
                        logger.exception(
                            "extension teardown failed during shutdown",
                            extra={"name": name},
                        )
                try:
                    await self.client.close()
                finally:
                    self.state = RuntimeState.CLOSED

    async def close(self) -> None:
        """Alias for stop, retained for client-style resource management."""
        await self.stop()

    async def wait_until_ready(self) -> None:
        """Wait until authentication, discovery, and on_ready have started."""
        if self.state is RuntimeState.CLOSED:
            raise BotClosed("bot was closed before becoming ready")
        await self._ready.wait()

    def is_ready(self) -> bool:
        """Return whether the runtime is currently accepting events."""
        return self.state is RuntimeState.RUNNING and self._ready.is_set()

    def is_closed(self) -> bool:
        """Return whether network resources have been permanently closed."""
        return self.state is RuntimeState.CLOSED

    async def _supervise_channel(self, target: ChannelTarget) -> None:
        backoff = 1.0
        while not self._closed:
            try:
                await self._consume_channel(target)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._closed:
                    return
                logger.exception(
                    "channel consumer failed",
                    extra={
                        "community_id": target.community_id,
                        "channel_id": target.channel_id,
                    },
                )
                await self._dispatch("on_disconnect", target, exc)
                delay = backoff
                await self._dispatch("on_reconnect", target, delay)
                await asyncio.sleep(delay)
                if self._closed:
                    return
                await self._dispatch("on_resumed", target)
                backoff = min(backoff * 2, self.max_consumer_backoff)

    async def _handle_message(self, event: MessageUpserted) -> None:
        message = event.message
        await self._dispatch("on_message", message)
        if not self._can_invoke_command(message):
            return
        try:
            parsed = self.command_adapter.parse(message.body, self.command_registry)
        except CommandNotFound:
            return
        except CommandError as exc:
            await self._dispatch_command_error(exc, None)
            return
        if parsed is None:
            return
        command, invocation = parsed
        context = Context(
            message=message,
            command=command.name,
            args=invocation.arguments,
            _messages=self.client.messages,
            invoked_with=invocation.invoked_with,
            prefix=invocation.prefix,
        )
        try:
            await self._dispatch("on_command", context)
            await self.command_pipeline.invoke(command, context, invocation.arguments)
            await self._dispatch("on_command_complete", context)
        except Exception as exc:
            await self._dispatch_command_error(exc, context)

    async def _consume_channel(self, target: ChannelTarget) -> None:
        stream_key = self.event_transport.stream_key(target)
        checkpoint = await self.cursor_store.load(stream_key)
        async for delivery in self.event_transport.listen(
            target,
            checkpoint=checkpoint,
            initial_after_seq=self.initial_after_seq,
        ):
            if self._closed:
                return
            event = delivery.event
            if isinstance(event, AccessLost):
                await self._dispatch("on_access_lost", event, target)
                await self.cursor_store.save(stream_key, delivery.checkpoint)
                return
            await self._handle_message(event)
            await self.cursor_store.save(stream_key, delivery.checkpoint)

    def _stream_key(self, target: ChannelTarget) -> str:
        """Return the event transport checkpoint key for compatibility."""
        return self.event_transport.stream_key(target)

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
        return self._matching_prefix(message.body) is not None

    def _matching_prefix(self, body: str) -> str | None:
        return self.command_adapter.matching_prefix(body)

    async def _dispatch_command_error(
        self,
        error: Exception,
        context: Context | None,
    ) -> None:
        handlers = self._events.get("on_command_error")
        if not handlers:
            await self._dispatch_error(error)
            return
        for handler in tuple(handlers):
            await handler(error, context)

    async def _dispatch(self, event_name: str, *args: Any) -> None:
        handlers = self._events.get(event_name)
        if not handlers:
            return
        for handler in tuple(handlers):
            try:
                await handler(*args)
            except Exception as exc:
                if event_name == "on_error":
                    raise
                await self._dispatch_error(exc)

    async def _dispatch_error(self, error: Exception) -> None:
        handlers = self._events.get("on_error")
        if not handlers:
            raise error
        for handler in tuple(handlers):
            await handler(error)

    @staticmethod
    def _ensure_async(handler: AsyncHandler) -> None:
        if not inspect.iscoroutinefunction(handler):
            raise TypeError("bot handlers must be async functions")
