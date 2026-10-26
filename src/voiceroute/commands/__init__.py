"""Transport-independent command framework primitives."""

from voiceroute.commands.context import Context
from voiceroute.commands.core import (
    Command,
    CommandInvocation,
    CommandParameter,
    CommandRegistry,
)
from voiceroute.commands.interactions import (
    ApplicationCommandHandler,
    ApplicationCommandRegistry,
    InteractionCallback,
    InteractionContext,
    application_command,
)
from voiceroute.commands.pipeline import (
    BucketType,
    Check,
    CommandPipeline,
    ConcurrencyLimit,
    Cooldown,
    Middleware,
    NextMiddleware,
    check,
    cooldown,
    max_concurrency,
)
from voiceroute.commands.prefix import PrefixCommandAdapter

__all__ = [
    "ApplicationCommandHandler",
    "ApplicationCommandRegistry",
    "BucketType",
    "Check",
    "Command",
    "CommandInvocation",
    "CommandParameter",
    "CommandPipeline",
    "CommandRegistry",
    "ConcurrencyLimit",
    "Context",
    "Cooldown",
    "InteractionCallback",
    "InteractionContext",
    "Middleware",
    "NextMiddleware",
    "PrefixCommandAdapter",
    "application_command",
    "check",
    "cooldown",
    "max_concurrency",
]
