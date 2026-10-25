"""Prefix-message adapter for the command framework."""

from __future__ import annotations

import shlex
from collections.abc import Sequence

from voiceroute.commands.core import Command, CommandInvocation, CommandRegistry
from voiceroute.errors import CommandParsingError


class PrefixCommandAdapter:
    """Convert a text message into a transport-neutral command invocation."""

    def __init__(self, prefixes: str | Sequence[str] = ("/", "!")) -> None:
        values = (prefixes,) if isinstance(prefixes, str) else tuple(prefixes)
        if not values or any(not prefix for prefix in values):
            raise ValueError("command prefixes must contain non-empty strings")
        self.prefixes = tuple(dict.fromkeys(sorted(values, key=len, reverse=True)))

    def matching_prefix(self, content: str) -> str | None:
        return next((prefix for prefix in self.prefixes if content.startswith(prefix)), None)

    def parse(
        self,
        content: str,
        registry: CommandRegistry,
    ) -> tuple[Command, CommandInvocation] | None:
        prefix = self.matching_prefix(content)
        if prefix is None:
            return None
        try:
            tokens = shlex.split(content[len(prefix) :])
        except ValueError as exc:
            raise CommandParsingError(str(exc)) from exc
        if not tokens:
            return None
        command, invocation = registry.resolve(tokens)
        return command, CommandInvocation(
            path=invocation.path,
            arguments=invocation.arguments,
            invoked_with=invocation.invoked_with,
            prefix=prefix,
        )
