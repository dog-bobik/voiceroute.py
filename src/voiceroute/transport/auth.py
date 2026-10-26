"""Authentication strategies for every Bot Platform credential surface."""

from __future__ import annotations

import base64
from typing import Protocol


class AuthStrategy(Protocol):
    """A credential strategy that can safely construct request headers."""

    def headers(self) -> dict[str, str]: ...


class BotAuth:
    """Build the VoiceRoute bot authorization header without exposing the token."""

    __slots__ = ("_token",)

    def __init__(self, token: str) -> None:
        if not token or not token.startswith("vrb_"):
            raise ValueError("token must be a VoiceRoute bot token starting with 'vrb_'")
        self._token = token

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bot {self._token}"}

    def __repr__(self) -> str:
        return "BotAuth(token=<redacted>)"


class BearerAuth:
    """OAuth 2 bearer authentication."""

    __slots__ = ("_token",)

    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("bearer token cannot be empty")
        self._token = token

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def __repr__(self) -> str:
        return "BearerAuth(token=<redacted>)"


class BasicAuth:
    """OAuth client authentication used only by token exchange endpoints."""

    __slots__ = ("_client_id", "_client_secret")

    def __init__(self, client_id: str, client_secret: str) -> None:
        if not client_id or not client_secret:
            raise ValueError("client_id and client_secret cannot be empty")
        self._client_id = client_id
        self._client_secret = client_secret

    def headers(self) -> dict[str, str]:
        value = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode(
            "ascii"
        )
        return {"Authorization": f"Basic {value}"}

    def __repr__(self) -> str:
        return "BasicAuth(client_id=<redacted>, client_secret=<redacted>)"


class PathCredentialAuth:
    """A secret embedded in a contract path, never in Authorization or logs."""

    __slots__ = ("_label", "_token")

    def __init__(self, token: str, *, label: str) -> None:
        if not token:
            raise ValueError("token cannot be empty")
        self._token = token
        self._label = label

    def headers(self) -> dict[str, str]:
        return {}

    def path_value(self) -> str:
        """Return the value only when constructing its exact contract path."""
        return self._token

    def __repr__(self) -> str:
        return f"{self._label}(token=<redacted>)"


class CallbackTokenAuth(PathCredentialAuth):
    def __init__(self, token: str) -> None:
        super().__init__(token, label="CallbackTokenAuth")


class WebhookSecretAuth(PathCredentialAuth):
    def __init__(self, secret: str) -> None:
        super().__init__(secret, label="WebhookSecretAuth")
