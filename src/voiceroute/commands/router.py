"""Composable command routers for organizing application handlers."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterator, Sequence
from dataclasses import replace
from typing import TypeVar

from voiceroute.commands.core import Command, CommandCallback, CommandRegistry
from voiceroute.commands.pipeline import Check, DependencyProvider, Middleware

HandlerT = TypeVar("HandlerT", bound=CommandCallback)


class Router:
    """A composable collection of prefix command declarations.

    Routers are declarative containers. A bot installs their commands into its
    existing registry and therefore continues to use one command pipeline.
    """

    def __init__(self, *, name: str | None = None) -> None:
        self.name = name or "router"
        self._commands: list[Command] = []
        self._routers: list[Router] = []
        self._filters: list[Check] = []
        self._middleware: list[Middleware] = []
        self._providers: dict[str, DependencyProvider] = {}

    @property
    def commands(self) -> tuple[Command, ...]:
        """Return commands declared by this router and its children."""
        return tuple(self.iter_commands())

    def iter_commands(self) -> Iterator[Command]:
        """Iterate declarations depth-first in registration order."""
        yield from self._iter_commands(())

    def _iter_commands(
        self,
        inherited_filters: tuple[Check, ...],
        inherited_middleware: tuple[Middleware, ...] = (),
        inherited_providers: tuple[tuple[str, DependencyProvider], ...] = (),
    ) -> Iterator[Command]:
        active_filters = (*inherited_filters, *self._filters)
        active_middleware = (*inherited_middleware, *self._middleware)
        active_providers = dict(inherited_providers)
        active_providers.update(self._providers)
        for command in self._commands:
            yield replace(
                command,
                checks=(*active_filters, *command.checks),
                middleware=(*active_middleware, *command.middleware),
                dependency_providers=tuple(
                    (*active_providers.items(), *command.dependency_providers)
                ),
            )
        for router in self._routers:
            yield from router._iter_commands(
                active_filters, active_middleware, tuple(active_providers.items())
            )

    def add_filter(self, predicate: Check) -> None:
        """Apply a check to every command declared in this router subtree."""
        if not callable(predicate):
            raise TypeError("router filter must be callable")
        self._filters.append(predicate)

    def add_middleware(self, middleware: Middleware) -> None:
        """Apply async middleware to all commands in this router subtree."""
        if not inspect.iscoroutinefunction(middleware):
            raise TypeError("router middleware must be an async function")
        self._middleware.append(middleware)

    def add_provider(self, name: str, provider: DependencyProvider) -> None:
        """Inject a root or per-command dependency throughout this router subtree."""
        if not name:
            raise ValueError("dependency name cannot be empty")
        if name in self._providers:
            raise ValueError(f"router dependency provider is already registered: {name}")
        self._providers[name] = provider

    def command(
        self,
        name: str | None = None,
        *,
        aliases: Sequence[str] = (),
        description: str | None = None,
        usage: str | None = None,
    ) -> Callable[[HandlerT], HandlerT]:
        """Declare a command using the same metadata as ``Bot.command``."""

        def decorator(callback: HandlerT) -> HandlerT:
            self._commands.append(
                Command.from_callback(
                    callback,
                    name=name,
                    aliases=aliases,
                    description=description,
                    usage=usage,
                )
            )
            return callback

        return decorator

    def include_router(self, router: Router) -> None:
        """Attach a child router, rejecting cycles and duplicate attachments."""
        if not isinstance(router, Router):
            raise TypeError("router must be a Router")
        if router is self or any(child is self for child in router._walk()):
            raise ValueError("including this router would create a cycle")
        if any(child is router for child in self._walk()):
            raise ValueError("router is already included")
        self._routers.append(router)

    def install(self, registry: CommandRegistry) -> tuple[Command, ...]:
        """Atomically add this tree to a command registry."""
        installed: list[Command] = []
        try:
            for command in self.iter_commands():
                registry.add(command)
                installed.append(command)
        except BaseException:
            for command in reversed(installed):
                registry.remove(command)
            raise
        return tuple(installed)

    def _walk(self) -> Iterator[Router]:
        yield self
        for router in self._routers:
            yield from router._walk()
