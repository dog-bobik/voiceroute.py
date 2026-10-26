"""High-level event-driven bot runtime."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Literal, TypeVar, cast

from voiceroute.client import VoiceRouteClient
from voiceroute.commands import (
    ApplicationCommandRegistry,
    Command,
    CommandPipeline,
    CommandRegistry,
    Context,
    InteractionCallback,
    InteractionContext,
    Middleware,
    PrefixCommandAdapter,
    application_command,
)
from voiceroute.errors import (
    BotAlreadyRunning,
    BotClosed,
    CommandError,
    CommandNotFound,
    ExtensionAlreadyLoaded,
    ExtensionNotLoaded,
    ExtensionSetupError,
    Forbidden,
    NoChannelsAvailable,
    NotFound,
)
from voiceroute.events import (
    AccessLost,
    CursorStore,
    EventDispatcher,
    EventTransport,
    InteractionCreated,
    InteractionEventTransport,
    InteractionSSETransport,
    InteractionTarget,
    LegacySSETransport,
    MemoryCursorStore,
    MessageUpserted,
)
from voiceroute.events.transport import ChannelTarget
from voiceroute.extensions import Extension, extension_command, listener_name
from voiceroute.gateway import GatewayCheckpointStore, GatewayClient, Intents
from voiceroute.models import (
    ApplicationCommand,
    BotIdentity,
    Channel,
    CommandOption,
    Community,
    Member,
    Message,
    PlatformEvent,
    Role,
)
from voiceroute.runtime import RuntimeState
from voiceroute.state import CachedEntity, CachePolicy, StateCache

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
        event_transport: EventTransport | Literal["auto", "gateway", "sse"] | None = None,
        interaction_event_transport: InteractionEventTransport | None = None,
        intents: Intents | None = None,
        gateway_store: GatewayCheckpointStore | None = None,
        gateway_client: GatewayClient | None = None,
        cache: StateCache | None = None,
        cache_policy: CachePolicy | None = None,
        sync_application_commands: bool = False,
        interaction_deduplication_size: int = 1024,
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
        if interaction_deduplication_size <= 0:
            raise ValueError("interaction_deduplication_size must be positive")
        if cache is not None and cache_policy is not None:
            raise ValueError("cache and cache_policy cannot be provided together")
        self.client = VoiceRouteClient(token=token, base_url=base_url)
        self.community_id = community_id
        self.channel_id = channel_id
        self.command_prefixes = self.command_adapter.prefixes
        self.max_event_streams = max_event_streams
        self.max_consumer_backoff = max_consumer_backoff
        self.initial_after_seq = initial_after_seq
        self.cursor_store = cursor_store or MemoryCursorStore()
        self.base_url = base_url.rstrip("/")
        self._event_transport_mode: str
        self.event_transport: EventTransport
        if isinstance(event_transport, str):
            self._event_transport_mode = event_transport
            self.event_transport = LegacySSETransport(
                self.client.events, self.client.messages, base_url=self.base_url
            )
        elif event_transport is None:
            self._event_transport_mode = "auto"
            self.event_transport = LegacySSETransport(
                self.client.events, self.client.messages, base_url=self.base_url
            )
        else:
            self._event_transport_mode = "custom"
            self.event_transport = event_transport
        self.intents = Intents.default() if intents is None else intents
        self.gateway_store = gateway_store
        self.gateway = gateway_client
        self.cache = cache or StateCache(cache_policy or CachePolicy())
        self.interaction_event_transport = interaction_event_transport or InteractionSSETransport(
            self.client.events,
            base_url=self.base_url,
        )
        self.sync_application_commands_on_start = sync_application_commands
        self.interaction_deduplication_size = interaction_deduplication_size
        self.user: BotIdentity | None = None
        self.listening_channels: tuple[ChannelTarget, ...] = ()
        self.command_registry = CommandRegistry()
        self.application_command_registry = ApplicationCommandRegistry()
        self.command_pipeline = CommandPipeline()
        self._events: dict[str, list[AsyncHandler]] = {}
        self.dispatcher = EventDispatcher(
            before_dispatch=self.cache.apply,
            dispatch_failed=self.cache.rollback,
            error_handler=self._handle_dispatch_error,
        )
        self.dispatcher.add_listener(self._handle_platform_event)
        self._extensions: dict[str, ExtensionRegistration] = {}
        self._extension_modules: dict[str, str] = {}
        self._consumer_tasks: set[asyncio.Task[None]] = set()
        self._processed_interaction_ids: set[str] = set()
        self._processed_interaction_order: deque[str] = deque()
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

    def slash_command(
        self,
        name: str,
        *,
        description: str,
        options: Sequence[CommandOption] = (),
        default_member_permissions: Sequence[str] = (),
    ) -> Callable[[InteractionCallback], InteractionCallback]:
        """Register a native application-command callback."""

        def decorator(handler: InteractionCallback) -> InteractionCallback:
            self._ensure_async(handler)
            self.application_command_registry.add(
                application_command(
                    name=name,
                    description=description,
                    callback=handler,
                    options=options,
                    default_member_permissions=default_member_permissions,
                )
            )
            return handler

        return decorator

    async def sync_application_commands(self) -> list[ApplicationCommand]:
        """Replace the remote registry with all locally declared slash commands."""
        if self.user is None:
            raise RuntimeError("bot identity is unavailable before start")
        return await self.client.application_commands.replace(
            self.user.application_id,
            self.application_command_registry.definitions,
        )

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
            if self.sync_application_commands_on_start:
                await self.sync_application_commands()
            if await self._should_use_gateway():
                await self._start_gateway()
                return
            self.listening_channels = tuple(await self._discover_channels())
            required_streams = len(self.listening_channels) + int(self._needs_interaction_stream())
            if required_streams > self.max_event_streams:
                raise NoChannelsAvailable(
                    f"runtime requires {required_streams} event streams, but max_event_streams is "
                    f"{self.max_event_streams}; reserve one stream for native interactions or "
                    "narrow the channel selection"
                )
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
            if self._needs_interaction_stream():
                self._consumer_tasks.add(
                    asyncio.create_task(
                        self._supervise_interactions(),
                        name="voiceroute:interactions",
                    )
                )
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
            if self.gateway is not None:
                await self.gateway.close()
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

    async def wait_for(
        self,
        event: str,
        *,
        check: Callable[[PlatformEvent], bool] | None = None,
        timeout: float | None = None,  # noqa: ASYNC109 - mirrors asyncio/discord.py wait_for
    ) -> PlatformEvent:
        """Wait for one matching Gateway event without a permanent listener."""
        return await self.dispatcher.wait_for(event, check=check, timeout=timeout)

    def get_community(self, community_id: str) -> CachedEntity | None:
        return self.cache.get_community(community_id)

    def get_channel(self, channel_id: str) -> CachedEntity | None:
        return self.cache.get_channel(channel_id)

    def get_role(self, role_id: str) -> CachedEntity | None:
        return self.cache.get_role(role_id)

    def get_member(self, community_id: str, user_id: str | int) -> CachedEntity | None:
        return self.cache.get_member(community_id, user_id)

    def get_thread(self, thread_id: str) -> CachedEntity | None:
        return self.cache.get_thread(thread_id)

    def get_message(
        self, community_id: str, channel_id: str, message_id_or_seq: str
    ) -> CachedEntity | None:
        return self.cache.get_message(community_id, channel_id, message_id_or_seq)

    async def fetch_community(self, community_id: str) -> Community:
        community = await self.client.communities.get(community_id)
        self.cache.store(
            "community",
            community.id,
            {"id": community.id, "name": community.name},
            partial=False,
        )
        return community

    async def fetch_channel(self, community_id: str, channel_id: str) -> Channel | None:
        channels = await self.client.communities.list_channels(community_id)
        channel = next((item for item in channels if item.id == channel_id), None)
        if channel is not None:
            self.cache.store(
                "channel",
                channel.id,
                {
                    "id": channel.id,
                    "communityId": community_id,
                    "name": channel.name,
                    "kind": channel.kind,
                },
                partial=False,
            )
        return channel

    async def fetch_member(self, community_id: str, user_id: int) -> Member | None:
        member = await self.client.members.get(community_id, user_id)
        if member is not None:
            self.cache.store(
                "member",
                f"{community_id}:{member.id}",
                {
                    "communityId": community_id,
                    "userId": str(member.id),
                    "displayName": member.display_name,
                    "roleIds": member.role_ids,
                },
                partial=False,
            )
        return member

    async def fetch_role(self, community_id: str, role_id: str) -> Role | None:
        roles = await self.client.roles.list(community_id)
        role = next((item for item in roles if item.id == role_id), None)
        if role is not None:
            self.cache.store(
                "role",
                role.id,
                {
                    "id": role.id,
                    "communityId": community_id,
                    "name": role.name,
                    "position": role.position,
                },
                partial=False,
            )
        return role

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
            except Forbidden as exc:
                if self._closed:
                    return
                logger.warning(
                    "channel event stream is unavailable: %s",
                    exc,
                    extra={
                        "community_id": target.community_id,
                        "channel_id": target.channel_id,
                    },
                )
                await self._dispatch("on_stream_unavailable", target, exc)
                return
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

    async def _supervise_interactions(self) -> None:
        backoff = 1.0
        target = InteractionTarget()
        while not self._closed:
            try:
                await self._consume_interactions(target)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._closed:
                    return
                logger.exception("interaction consumer failed")
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
            _members=self.client.members,
            _communities=self.client.communities,
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
            if not isinstance(event, MessageUpserted):
                continue
            await self._handle_message(event)
            await self.cursor_store.save(stream_key, delivery.checkpoint)

    async def _consume_interactions(self, target: InteractionTarget) -> None:
        stream_key = self.interaction_event_transport.stream_key(target)
        checkpoint = await self.cursor_store.load(stream_key)
        async for delivery in self.interaction_event_transport.listen(
            target,
            checkpoint=checkpoint,
            initial_after_seq=None,
        ):
            if self._closed:
                return
            event = delivery.event
            if isinstance(event, AccessLost):
                await self._dispatch("on_access_lost", event, target)
                await self.cursor_store.save(stream_key, delivery.checkpoint)
                return
            if not isinstance(event, InteractionCreated):
                continue
            await self._handle_interaction(event)
            await self.cursor_store.save(stream_key, delivery.checkpoint)

    async def _handle_interaction(self, event: InteractionCreated) -> None:
        interaction_id = event.interaction.id
        if interaction_id in self._processed_interaction_ids:
            return
        context = InteractionContext(
            event.interaction,
            self.client.interactions,
            self.client.members,
        )
        await self._dispatch("on_interaction", context)
        command = self.application_command_registry.get(event.interaction.command.name)
        if command is None:
            self._remember_interaction(interaction_id)
            return
        try:
            await self._dispatch("on_application_command", context)
            await command.callback(context)
            await self._dispatch("on_application_command_complete", context)
            self._remember_interaction(interaction_id)
        except Exception as exc:
            handlers = self._events.get("on_application_command_error")
            if not handlers:
                await self._dispatch_error(exc)
                return
            for handler in tuple(handlers):
                await handler(exc, context)

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

    async def _should_use_gateway(self) -> bool:
        if self._event_transport_mode in {"sse", "custom"}:
            return False
        if self._event_transport_mode == "gateway" or self.gateway is not None:
            return True
        try:
            capabilities = await self.client.platform.capabilities()
        except NotFound:
            return False
        return capabilities.supports("gateway")

    async def _start_gateway(self) -> None:
        if self.gateway is None:
            self.gateway = self.client.gateway(intents=self.intents, store=self.gateway_store)
        self.gateway.on_session_invalidated = self._reconcile_state

        async def dispatch(event: PlatformEvent) -> None:
            await self.dispatcher.dispatch(event)

        task = asyncio.create_task(self.gateway.run(dispatch), name="voiceroute:gateway")
        self._consumer_tasks = {task}
        ready = asyncio.create_task(self.gateway.wait_until_ready())
        done, _ = await asyncio.wait({task, ready}, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            ready.cancel()
            await task
        await ready
        if self.cache.policy.reconcile_on_ready:
            await self.cache.reconcile(self.client)
        if self._needs_legacy_message_streams():
            self.listening_channels = tuple(await self._discover_channels())
            required_streams = len(self.listening_channels) + int(self._needs_interaction_stream())
            if required_streams > self.max_event_streams:
                raise NoChannelsAvailable(
                    f"compatibility runtime requires {required_streams} SSE streams, but "
                    f"max_event_streams is {self.max_event_streams}"
                )
            self._consumer_tasks.update(
                asyncio.create_task(
                    self._supervise_channel(target),
                    name=f"voiceroute:legacy:{target.community_id}:{target.channel_id}",
                )
                for target in self.listening_channels
            )
        if self._needs_interaction_stream():
            self._consumer_tasks.add(
                asyncio.create_task(
                    self._supervise_interactions(),
                    name="voiceroute:legacy-interactions",
                )
            )
        await self._dispatch("on_connect")
        self.state = RuntimeState.RUNNING
        self._ready.set()
        await self._dispatch("on_ready")
        await task

    def _needs_legacy_message_streams(self) -> bool:
        return bool(self.command_registry.commands or self._events.get("on_message"))

    async def _handle_platform_event(self, event: PlatformEvent) -> None:
        await self._dispatch("on_raw_event", event)
        await self._dispatch(f"on_{event.name.casefold()}", event)
        change = self.cache.change_for(event)
        if change is not None:
            await self._dispatch_cache_change(event.name, change.before, change.after)
        if not event.is_known:
            await self._dispatch("on_unknown_event", event)

    async def _dispatch_cache_change(
        self,
        event_name: str,
        before: CachedEntity | None,
        after: CachedEntity | None,
    ) -> None:
        if event_name == "MEMBER_JOINED" and after is not None:
            await self._dispatch("on_member_join", after)
        elif event_name == "MEMBER_LEFT" and before is not None:
            await self._dispatch("on_member_remove", before)
        elif event_name.endswith("_CREATED") and after is not None:
            kind = event_name.removesuffix("_CREATED").casefold()
            await self._dispatch(f"on_{kind}_create", after)
        elif event_name.endswith("_UPDATED") and after is not None:
            kind = event_name.removesuffix("_UPDATED").casefold()
            await self._dispatch(f"on_{kind}_update", before, after)
        elif event_name.endswith("_DELETED") and before is not None:
            kind = event_name.removesuffix("_DELETED").casefold()
            await self._dispatch(f"on_{kind}_delete", before)

    async def _reconcile_state(self) -> None:
        await self.cache.reconcile(self.client)

    async def _handle_dispatch_error(self, error: Exception, event: PlatformEvent) -> None:
        handlers = self._events.get("on_event_error")
        if not handlers:
            await self._dispatch_error(error)
            return
        for handler in tuple(handlers):
            await handler(error, event)

    def _needs_interaction_stream(self) -> bool:
        return bool(
            self.application_command_registry.commands
            or self._events.get("on_interaction")
            or self._events.get("on_application_command")
        )

    def _remember_interaction(self, interaction_id: str) -> None:
        if interaction_id in self._processed_interaction_ids:
            return
        self._processed_interaction_ids.add(interaction_id)
        self._processed_interaction_order.append(interaction_id)
        if len(self._processed_interaction_order) > self.interaction_deduplication_size:
            expired = self._processed_interaction_order.popleft()
            self._processed_interaction_ids.remove(expired)

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
