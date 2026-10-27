"""Transport-independent command framework primitives."""

from voiceroute.commands.components import ComponentCallback, ComponentRouter
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
    bot_has_permissions,
    check,
    cooldown,
    has_permissions,
    is_owner,
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
    "ComponentCallback",
    "ComponentRouter",
    "ConcurrencyLimit",
    "Context",
    "Cooldown",
    "InteractionCallback",
    "InteractionContext",
    "Middleware",
    "NextMiddleware",
    "PrefixCommandAdapter",
    "application_command",
    "bot_has_permissions",
    "check",
    "cooldown",
    "has_permissions",
    "is_owner",
    "max_concurrency",
]
