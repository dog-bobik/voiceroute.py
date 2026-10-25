"""Public exception hierarchy."""

from dataclasses import dataclass
from typing import Any


class VoiceRouteError(Exception):
    """Base exception raised by the library."""


@dataclass(eq=False)
class HTTPError(VoiceRouteError):
    """An unsuccessful response from VoiceRoute."""

    status_code: int
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None

    def __str__(self) -> str:
        return f"VoiceRoute API returned {self.status_code}: {self.message}"


class BadRequest(HTTPError):
    """The request was invalid."""


class Unauthorized(HTTPError):
    """The bot token is missing, invalid, or revoked."""


class Forbidden(HTTPError):
    """The bot is not allowed to perform the action."""


class NotFound(HTTPError):
    """The resource does not exist or is hidden from the bot."""


class Conflict(HTTPError):
    """The operation conflicts with the current resource state."""


class ValidationError(HTTPError):
    """The request was rejected by a content validation rule."""


class RateLimited(HTTPError):
    """The API rate limit was reached."""

    retry_after: float | None

    def __init__(
        self,
        status_code: int,
        message: str,
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(status_code, message, details, request_id)
        self.retry_after = retry_after


class ServiceUnavailable(HTTPError):
    """A VoiceRoute dependency is temporarily unavailable."""


class TransportError(VoiceRouteError):
    """The request could not be completed at the network layer."""


class SSEError(VoiceRouteError):
    """An SSE stream returned malformed or unsupported data."""


class CursorStoreError(VoiceRouteError):
    """A durable event checkpoint could not be read or written."""


class NoChannelsAvailable(VoiceRouteError):
    """The bot cannot discover any accessible text channels."""


class ClientClosedError(VoiceRouteError):
    """An operation was attempted after closing the client."""


class CommandError(VoiceRouteError):
    """Base exception raised while resolving or invoking a command."""


class CommandParsingError(CommandError):
    """A prefix command could not be tokenized."""


class CommandNotFound(CommandError):
    """No registered command matches an invocation."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"command is not registered: {name}")


class MissingRequiredArgument(CommandError):
    """A required positional argument was omitted."""

    def __init__(self, command: str, parameter: str) -> None:
        self.command = command
        self.parameter = parameter
        super().__init__(f"{command}: missing required argument {parameter}")


class TooManyArguments(CommandError):
    """An invocation contains more arguments than the command accepts."""

    def __init__(self, command: str, arguments: tuple[str, ...]) -> None:
        self.command = command
        self.arguments = arguments
        super().__init__(f"{command}: too many arguments")


class BadArgument(CommandError):
    """An argument could not be converted to its declared type."""

    def __init__(self, parameter: str, value: str, expected_type: str) -> None:
        self.parameter = parameter
        self.value = value
        self.expected_type = expected_type
        super().__init__(f"{parameter}: expected {expected_type}, received {value!r}")


class UnsupportedCommandParameter(CommandError):
    """A callback parameter cannot be represented by the command framework."""

    def __init__(self, parameter: str, reason: str) -> None:
        self.parameter = parameter
        self.reason = reason
        super().__init__(f"unsupported command parameter {parameter}: {reason}")
