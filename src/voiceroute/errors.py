"""Public exception hierarchy."""

from dataclasses import dataclass
from typing import Any


class VoiceRouteError(Exception):
    """Base exception raised by the library."""


@dataclass(frozen=True, slots=True)
class FieldError:
    """One machine-readable validation failure returned by Bot Platform v1."""

    field: str
    code: str
    message: str | None = None


@dataclass(eq=False)
class HTTPError(VoiceRouteError):
    """An unsuccessful response from VoiceRoute."""

    status_code: int
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None
    code: str | None = None
    retryable: bool = False
    field_errors: tuple[FieldError, ...] = ()

    def __str__(self) -> str:
        return f"VoiceRoute API returned {self.status_code}: {self.message}"


class BadRequest(HTTPError):
    """The request was invalid."""


class Unauthorized(HTTPError):
    """The bot token is missing, invalid, or revoked."""


class AuthenticationRequired(Unauthorized):
    """The operation requires an authenticated user or application."""


class BotAuthenticationRequired(Unauthorized):
    """The operation specifically requires a bot credential."""


class Forbidden(HTTPError):
    """The bot is not allowed to perform the action."""


class MissingPermission(Forbidden):
    """The authenticated principal lacks a required VoiceRoute permission."""


class NotFound(HTTPError):
    """The resource does not exist or is hidden from the bot."""


class Conflict(HTTPError):
    """The operation conflicts with the current resource state."""


class ResourceVersionConflict(Conflict):
    """A conditional v1 mutation used a stale resource version."""


class VersionConflict(ResourceVersionConflict):
    """A conditional mutation used a stale version or ETag."""


class IdempotencyConflict(Conflict):
    """An idempotency key was reused with a different request payload."""


class PayloadTooLarge(HTTPError):
    """The request or response exceeds a platform or client size limit."""


class RequestCapacity(HTTPError):
    """The platform temporarily has no capacity for the request."""


class HTTPFeatureUnavailable(HTTPError):
    """The deployment does not expose a requested HTTP feature."""


class FeatureUnavailable(VoiceRouteError):
    """The connected deployment does not expose a requested capability."""


class GatewayError(VoiceRouteError):
    """The Gateway connection or protocol failed."""


class GatewayClosed(GatewayError):
    """The Gateway closed with a terminal protocol code."""

    def __init__(self, code: int, reason: str = "") -> None:
        self.code = code
        self.reason = reason
        super().__init__(f"Gateway closed with code {code}: {reason}")


class GatewayProtocolError(GatewayError):
    """The Gateway sent a malformed or unsupported required frame."""


class InstallationGrantRequired(GatewayError):
    """No active installation granted one or more requested capabilities."""

    def __init__(self, capabilities: tuple[str, ...]) -> None:
        self.capabilities = capabilities
        super().__init__(
            "Gateway capabilities require an active installation grant: "
            + ", ".join(capabilities)
            + "; remove and reinstall the bot to change installation grants"
        )

    @property
    def intents(self) -> tuple[str, ...]:
        """Compatibility alias for the pre-grants experimental API."""
        return self.capabilities


# Compatibility aliases for callers of the pre-grants experimental API.
IntentNotEnabled = InstallationGrantRequired
PrivilegedIntentRequired = InstallationGrantRequired


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
        *,
        code: str | None = None,
        retryable: bool = True,
        field_errors: tuple[FieldError, ...] = (),
    ) -> None:
        super().__init__(status_code, message, details, request_id, code, retryable, field_errors)
        self.retry_after = retry_after


class ServiceUnavailable(HTTPError):
    """A VoiceRoute dependency is temporarily unavailable."""


class TransportError(VoiceRouteError):
    """The request could not be completed at the network layer."""


class ResponseTooLarge(TransportError):
    """A response exceeded the configured in-memory safety limit."""


class UnexpectedRedirect(TransportError):
    """A credentialed request received a redirect that was not followed."""


class SSEError(VoiceRouteError):
    """An SSE stream returned malformed or unsupported data."""


class CursorStoreError(VoiceRouteError):
    """A durable event checkpoint could not be read or written."""


class NoChannelsAvailable(VoiceRouteError):
    """The bot cannot discover any accessible text channels."""


class ClientClosedError(VoiceRouteError):
    """An operation was attempted after closing the client."""


class BotAlreadyRunning(VoiceRouteError):
    """The same Bot instance is already starting or running."""


class BotClosed(VoiceRouteError):
    """A closed Bot instance cannot be started again."""


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


class CheckFailure(CommandError):
    """A command predicate rejected an invocation."""

    def __init__(self, command: str, check: str) -> None:
        self.command = command
        self.check = check
        super().__init__(f"{command}: check failed: {check}")


class CommandOnCooldown(CommandError):
    """A command exceeded its configured invocation rate."""

    def __init__(self, command: str, retry_after: float) -> None:
        self.command = command
        self.retry_after = retry_after
        super().__init__(f"{command}: retry after {retry_after:.3f} seconds")


class MaxConcurrencyReached(CommandError):
    """A command already has the maximum number of active invocations."""

    def __init__(self, command: str, limit: int, bucket: str) -> None:
        self.command = command
        self.limit = limit
        self.bucket = bucket
        super().__init__(f"{command}: maximum concurrency {limit} reached for {bucket}")


class ExtensionError(VoiceRouteError):
    """Base exception raised while managing an extension."""


class ExtensionAlreadyLoaded(ExtensionError):
    """An extension with the same qualified name is already active."""


class ExtensionNotLoaded(ExtensionError):
    """The requested extension or module is not active."""


class ExtensionSetupError(ExtensionError):
    """An extension module does not expose a valid setup contract."""
