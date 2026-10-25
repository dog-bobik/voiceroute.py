"""Asynchronous HTTP transport."""

import asyncio
import random
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
from voiceroute.transport.rate_limit import RateLimiter

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

    def __init__(
        self,
        *,
        token: str,
        base_url: str,
        timeout: float,
        rate_limiter: RateLimiter | None = None,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        auth = BotAuth(token)
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={**auth.headers(), "Accept": "application/json"},
            timeout=timeout,
        )
        self._rate_limiter = rate_limiter or RateLimiter()
        self._max_attempts = max_attempts
        self._closed = False

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int | None] | None = None,
        json: Any = None,
        retryable: bool | None = None,
    ) -> dict[str, Any] | None:
        if self._closed:
            raise ClientClosedError("the VoiceRoute client is closed")

        can_retry = (
            retryable if retryable is not None else method.upper() in {"GET", "HEAD", "OPTIONS"}
        )
        response: httpx.Response | None = None
        for attempt in range(1, self._max_attempts + 1):
            await self._rate_limiter.acquire()
            try:
                response = await self._client.request(
                    method,
                    path,
                    params=self._clean_params(params),
                    json=json,
                )
            except httpx.HTTPError as exc:
                if can_retry and attempt < self._max_attempts:
                    await self._sleep_before_retry(attempt)
                    continue
                raise TransportError("VoiceRoute request failed") from exc

            if response.status_code == 429 and attempt < self._max_attempts:
                await self._sleep_for_rate_limit(response, attempt)
                continue
            if response.status_code == 503 and can_retry and attempt < self._max_attempts:
                await self._sleep_before_retry(attempt)
                continue
            break

        if response is None:
            raise TransportError("VoiceRoute request produced no response")

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

        await self._rate_limiter.acquire()
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

    async def _sleep_for_rate_limit(self, response: httpx.Response, attempt: int) -> None:
        retry_after = self._parse_retry_after(response)
        if retry_after is None:
            await self._sleep_before_retry(attempt)
        else:
            await asyncio.sleep(retry_after)

    @staticmethod
    async def _sleep_before_retry(attempt: int) -> None:
        maximum = min(0.5 * (2 ** (attempt - 1)), 5.0)
        await asyncio.sleep(random.uniform(0.0, maximum))

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float | None:
        raw_value = response.headers.get("Retry-After")
        if raw_value is None:
            return None
        try:
            return max(0.0, float(raw_value))
        except ValueError:
            return None
