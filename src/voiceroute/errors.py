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


class ClientClosedError(VoiceRouteError):
    """An operation was attempted after closing the client."""
