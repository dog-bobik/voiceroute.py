"""Asynchronous HTTP transport."""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

import httpx

from voiceroute.errors import (
    BadRequest,
    ClientClosedError,
    Conflict,
    Forbidden,
    HTTPError,
    NotFound,
    RateLimited,
    ServiceUnavailable,
    TransportError,
    Unauthorized,
    ValidationError,
)
from voiceroute.transport.auth import BotAuth

_ERRORS: dict[int, type[HTTPError]] = {
    400: BadRequest,
    401: Unauthorized,
    403: Forbidden,
    404: NotFound,
    409: Conflict,
    422: ValidationError,
    429: RateLimited,
    503: ServiceUnavailable,
}


class HTTPTransport:
    """Small HTTP layer shared by all resource APIs."""

    def __init__(self, *, token: str, base_url: str, timeout: float) -> None:
        auth = BotAuth(token)
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={**auth.headers(), "Accept": "application/json"},
            timeout=timeout,
        )
        self._closed = False

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int | None] | None = None,
        json: Any = None,
    ) -> dict[str, Any] | None:
        if self._closed:
            raise ClientClosedError("the VoiceRoute client is closed")

        try:
            response = await self._client.request(
                method,
                path,
                params=self._clean_params(params),
                json=json,
            )
        except httpx.HTTPError as exc:
            raise TransportError("VoiceRoute request failed") from exc

        if response.is_error:
            self._raise_for_response(response)
        if response.status_code == 204:
            return None

        try:
            payload = response.json()
        except ValueError as exc:
            raise TransportError("VoiceRoute returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise TransportError("VoiceRoute returned a non-object JSON response")
        return payload

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._client.aclose()

    @asynccontextmanager
    async def stream(
        self,
        path: str,
        *,
        params: Mapping[str, str | int | None] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> AsyncIterator[httpx.Response]:
        """Open an authenticated streaming response."""
        if self._closed:
            raise ClientClosedError("the VoiceRoute client is closed")

        try:
            async with self._client.stream(
                "GET",
                path,
                params=self._clean_params(params),
                headers=headers,
            ) as response:
                if response.is_error:
                    await response.aread()
                    self._raise_for_response(response)
                yield response
        except httpx.HTTPError as exc:
            raise TransportError("VoiceRoute stream failed") from exc

    @staticmethod
    def _raise_for_response(response: httpx.Response) -> None:
        try:
            body = response.json()
        except ValueError:
            body = {}
        details = body if isinstance(body, dict) else None
        message = str(details.get("error", "Unknown API error")) if details else "Unknown API error"
        request_id = response.headers.get("X-Request-ID")
        error_type = _ERRORS.get(response.status_code, HTTPError)

        if error_type is RateLimited:
            raw_retry_after = response.headers.get("Retry-After")
            try:
                retry_after = float(raw_retry_after) if raw_retry_after is not None else None
            except ValueError:
                retry_after = None
            raise RateLimited(
                response.status_code,
                message,
                details,
                request_id,
                retry_after,
            )
        raise error_type(response.status_code, message, details, request_id)

    @staticmethod
    def _clean_params(
        params: Mapping[str, str | int | None] | None,
    ) -> dict[str, str | int] | None:
        if params is None:
            return None
        return {key: value for key, value in params.items() if value is not None}
