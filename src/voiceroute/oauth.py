"""OAuth 2 authorization-code with PKCE client, separate from Bot credentials."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlencode

from voiceroute.api.private_messages import PrivateMessagesAPI
from voiceroute.transport import AuthStrategy, BasicAuth, BearerAuth, HTTPTransport


class OAuthTokenStore(Protocol):
    """Secure storage contract for rotating OAuth refresh tokens."""

    async def save_refresh_token(self, application_id: str, token: str) -> None: ...

    async def load_refresh_token(self, application_id: str) -> str | None: ...

    async def delete_refresh_token(self, application_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    url: str
    state: str
    code_verifier: str = field(repr=False)

    def matches_state(self, response_state: str) -> bool:
        """Compare the callback state without a timing-sensitive string check."""
        return hmac.compare_digest(self.state, response_state)


@dataclass(frozen=True, slots=True)
class OAuthTokens:
    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    expires_in: int = 3600
    token_type: str = "Bearer"
    scope: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> OAuthTokens:
        return cls(
            access_token=str(data["access_token"]),
            refresh_token=(
                str(data["refresh_token"]) if data.get("refresh_token") is not None else None
            ),
            expires_in=int(data.get("expires_in", 3600)),
            token_type=str(data.get("token_type", "Bearer")),
            scope=str(data.get("scope", "")),
        )

    def __repr__(self) -> str:
        return (
            "OAuthTokens(access_token=<redacted>, refresh_token=<redacted>, "
            f"expires_in={self.expires_in}, scope={self.scope!r})"
        )


class _NoAuth:
    def headers(self) -> dict[str, str]:
        return {}


class OAuthClient:
    """Perform OAuth code and refresh flows without sharing BotAuth credentials."""

    def __init__(
        self,
        application_id: str,
        *,
        client_secret: str | None = None,
        base_url: str = "https://voiceroute.cc",
        timeout: float = 30.0,
    ) -> None:
        if not application_id:
            raise ValueError("application_id cannot be empty")
        self.application_id = application_id
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client_secret = client_secret
        auth: AuthStrategy = (
            BasicAuth(application_id, client_secret) if client_secret else _NoAuth()
        )
        self._transport = HTTPTransport(
            auth=auth,
            base_url=self._base_url,
            timeout=timeout,
        )

    def __repr__(self) -> str:
        return f"OAuthClient(application_id={self.application_id!r}, client_secret=<redacted>)"

    def authorization_request(
        self,
        redirect_uri: str,
        scopes: Sequence[str],
        *,
        state: str | None = None,
    ) -> AuthorizationRequest:
        if not redirect_uri or not scopes:
            raise ValueError("redirect_uri and at least one scope are required")
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        request_state = state or secrets.token_urlsafe(32)
        query = urlencode(
            {
                "client_id": self.application_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "scope": " ".join(dict.fromkeys(scopes)),
                "state": request_state,
                "code_challenge": challenge.decode("ascii").rstrip("="),
                "code_challenge_method": "S256",
            }
        )
        return AuthorizationRequest(
            url=f"{self._base_url}/api/v1/oauth2/authorize?{query}",
            state=request_state,
            code_verifier=verifier,
        )

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> OAuthTokens:
        if not code or not code_verifier:
            raise ValueError("code and code_verifier are required")
        body: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
        if self._client_secret is None:
            body["client_id"] = self.application_id
        payload = await self._transport.request("POST", "/api/v1/oauth2/token", json=body)
        return OAuthTokens.from_dict(_required_payload(payload))

    async def refresh(self, store: OAuthTokenStore) -> OAuthTokens:
        refresh_token = await store.load_refresh_token(self.application_id)
        if refresh_token is None:
            raise RuntimeError("no OAuth refresh token is stored for this application")
        body = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        if self._client_secret is None:
            body["client_id"] = self.application_id
        payload = await self._transport.request("POST", "/api/v1/oauth2/token", json=body)
        tokens = OAuthTokens.from_dict(_required_payload(payload))
        if tokens.refresh_token is None:
            raise RuntimeError("VoiceRoute did not return the rotated OAuth refresh token")
        await store.save_refresh_token(self.application_id, tokens.refresh_token)
        return tokens

    async def authorization(self, access_token: str) -> dict[str, Any]:
        transport = HTTPTransport(
            auth=BearerAuth(access_token),
            base_url=self._base_url,
            timeout=self._timeout,
        )
        try:
            payload = await transport.request("GET", "/api/v1/oauth2/@me")
        finally:
            await transport.close()
        return payload or {}

    def private_messages(self, access_token: str) -> OAuthPrivateMessagesAPI:
        """Create a separately bearer-authenticated DM API for granted scopes."""
        transport = HTTPTransport(
            auth=BearerAuth(access_token), base_url=self._base_url, timeout=self._timeout
        )
        return OAuthPrivateMessagesAPI(transport, self.application_id)

    async def close(self) -> None:
        await self._transport.close()

    async def __aenter__(self) -> OAuthClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()


def _required_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        raise RuntimeError("VoiceRoute returned no OAuth token payload")
    return payload


class OAuthPrivateMessagesAPI(PrivateMessagesAPI):
    """Bearer-authenticated private messaging API that owns its transport."""

    async def close(self) -> None:
        await self._transport.close()

    async def __aenter__(self) -> OAuthPrivateMessagesAPI:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
