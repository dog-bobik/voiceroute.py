"""Asynchronous HTTP transport for legacy and Bot Platform v1 APIs."""

import asyncio
import random
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx

from voiceroute.errors import (
    AuthenticationRequired,
    BadRequest,
    BotAuthenticationRequired,
    ClientClosedError,
    Conflict,
    FieldError,
    Forbidden,
    HTTPError,
    HTTPFeatureUnavailable,
    IdempotencyConflict,
    MissingPermission,
    NotFound,
    PayloadTooLarge,
    RateLimited,
    RequestCapacity,
    ResponseTooLarge,
    ServiceUnavailable,
    TransportError,
    Unauthorized,
    UnexpectedRedirect,
    ValidationError,
    VersionConflict,
)
from voiceroute.transport.auth import AuthStrategy, BotAuth
from voiceroute.transport.rate_limit import RateLimiter

_ERRORS: dict[int, type[HTTPError]] = {
    400: BadRequest,
    401: Unauthorized,
    403: Forbidden,
    404: NotFound,
    409: Conflict,
    413: PayloadTooLarge,
    422: ValidationError,
    429: RateLimited,
    503: ServiceUnavailable,
}

_ERROR_CODES: dict[str, type[HTTPError]] = {
    "AUTHENTICATION_REQUIRED": AuthenticationRequired,
    "BOT_AUTHENTICATION_REQUIRED": BotAuthenticationRequired,
    "MISSING_PERMISSION": MissingPermission,
    "RESOURCE_VERSION_CONFLICT": VersionConflict,
    "VERSION_CONFLICT": VersionConflict,
    "IDEMPOTENCY_CONFLICT": IdempotencyConflict,
    "IDEMPOTENCY_KEY_REUSED": IdempotencyConflict,
    "PAYLOAD_TOO_LARGE": PayloadTooLarge,
    "REQUEST_CAPACITY": RequestCapacity,
    "FEATURE_UNAVAILABLE": HTTPFeatureUnavailable,
}


@dataclass(frozen=True, slots=True)
class RateLimitMetadata:
    """Rate-limit metadata attached to a VoiceRoute response."""

    limit: int | None = None
    remaining: int | None = None
    reset_after: float | None = None
    bucket: str | None = None
    scope: str | None = None


@dataclass(frozen=True, slots=True)
class HTTPResult:
    """JSON payload together with Bot Platform v1 response metadata."""

    payload: dict[str, Any] | None
    status_code: int
    request_id: str | None
    api_version: str | None
    etag: str | None
    rate_limit: RateLimitMetadata


class HTTPTransport:
    """Small HTTP layer shared by legacy and v1 resource APIs."""

    def __init__(
        self,
        *,
        token: str | None = None,
        base_url: str,
        timeout: float,
        rate_limiter: RateLimiter | None = None,
        max_attempts: int = 3,
        auth: AuthStrategy | None = None,
        api_version: str = "1",
        max_concurrency: int = 100,
        max_response_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        if auth is not None and token is not None:
            raise ValueError("pass either token or auth, not both")
        if auth is None and token is None:
            raise ValueError("token or auth is required")
        credential = auth if auth is not None else BotAuth(token or "")
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                **credential.headers(),
                "Accept": "application/json",
                "X-VoiceRoute-API-Version": api_version,
            },
            timeout=timeout,
            follow_redirects=False,
        )
        self._rate_limiter = rate_limiter or RateLimiter()
        self._max_attempts = max_attempts
        self._closed = False
        self._concurrency = asyncio.Semaphore(max_concurrency)
        self._max_response_bytes = max_response_bytes
        self.last_rate_limit = RateLimitMetadata()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int | None] | None = None,
        json: Any = None,
        retryable: bool | None = None,
        idempotency_key: str | None = None,
        if_match: str | None = None,
        headers: Mapping[str, str] | None = None,
        generate_idempotency_key: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Return JSON while preserving the original public transport contract."""
        result = await self.request_with_response(
            method,
            path,
            params=params,
            json=json,
            retryable=retryable,
            idempotency_key=idempotency_key,
            if_match=if_match,
            headers=headers,
            generate_idempotency_key=generate_idempotency_key,
            request_id=request_id,
        )
        return result.payload

    async def request_with_response(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int | None] | None = None,
        json: Any = None,
        retryable: bool | None = None,
        idempotency_key: str | None = None,
        if_match: str | None = None,
        headers: Mapping[str, str] | None = None,
        generate_idempotency_key: bool = False,
        request_id: str | None = None,
    ) -> HTTPResult:
        """Return JSON and version, request, ETag, and rate-limit metadata."""
        if self._closed:
            raise ClientClosedError("the VoiceRoute client is closed")

        method = method.upper()
        if generate_idempotency_key:
            if method in {"GET", "HEAD", "OPTIONS"}:
                raise ValueError("idempotency keys are only valid for mutations")
            if idempotency_key is not None:
                raise ValueError("pass either idempotency_key or generate_idempotency_key")
            idempotency_key = str(uuid.uuid4())
        can_retry = (
            retryable
            if retryable is not None
            else method in {"GET", "HEAD", "OPTIONS"} or idempotency_key is not None
        )
        request_headers = dict(headers or {})
        if idempotency_key is not None:
            request_headers["Idempotency-Key"] = idempotency_key
        if if_match is not None:
            request_headers["If-Match"] = if_match
        if request_id is not None:
            request_headers["X-Request-ID"] = request_id

        response: httpx.Response | None = None
        for attempt in range(1, self._max_attempts + 1):
            await self._rate_limiter.acquire()
            try:
                async with self._concurrency:
                    response = await self._request_limited(
                        method,
                        path,
                        params=self._clean_params(params),
                        json=json,
                        headers=request_headers or None,
                    )
            except httpx.HTTPError as exc:
                if can_retry and attempt < self._max_attempts:
                    await self._sleep_before_retry(attempt)
                    continue
                raise TransportError("VoiceRoute request failed") from exc

            if response.status_code == 429 and can_retry and attempt < self._max_attempts:
                await self._sleep_for_rate_limit(response, attempt)
                continue
            if response.status_code == 503 and can_retry and attempt < self._max_attempts:
                await self._sleep_for_rate_limit(response, attempt)
                continue
            break

        if response is None:
            raise TransportError("VoiceRoute request produced no response")

        if response.is_redirect:
            raise UnexpectedRedirect(
                f"VoiceRoute returned redirect {response.status_code}; "
                "credentials were not forwarded"
            )
        self.last_rate_limit = self._rate_limit_metadata(response)
        if response.is_error:
            self._raise_for_response(response)
        if response.status_code == 204:
            return self._result(response, None)

        try:
            payload = response.json()
        except ValueError as exc:
            raise TransportError("VoiceRoute returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise TransportError("VoiceRoute returned a non-object JSON response")
        return self._result(response, payload)

    async def close(self) -> None:
        """Close the underlying HTTP client once."""
        if not self._closed:
            self._closed = True
            await self._client.aclose()

    async def _request_limited(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int] | None,
        json: Any,
        headers: Mapping[str, str] | None,
    ) -> httpx.Response:
        request = self._client.build_request(
            method, path, params=params, json=json, headers=headers
        )
        response = await self._client.send(request, stream=True)
        content_length = _optional_int(response.headers.get("Content-Length"))
        if content_length is not None and content_length > self._max_response_bytes:
            await response.aclose()
            raise ResponseTooLarge(
                f"VoiceRoute response is larger than {self._max_response_bytes} bytes"
            )
        body = bytearray()
        try:
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > self._max_response_bytes:
                    raise ResponseTooLarge(
                        f"VoiceRoute response is larger than {self._max_response_bytes} bytes"
                    )
        finally:
            await response.aclose()
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            content=bytes(body),
            request=request,
            extensions=response.extensions,
        )

    @asynccontextmanager
    async def stream(
        self,
        path: str,
        *,
        params: Mapping[str, str | int | None] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> AsyncIterator[httpx.Response]:
        """Open an authenticated legacy streaming response."""
        if self._closed:
            raise ClientClosedError("the VoiceRoute client is closed")

        await self._rate_limiter.acquire()
        try:
            async with self._client.stream(
                "GET", path, params=self._clean_params(params), headers=headers
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
        envelope = body if isinstance(body, dict) else {}
        raw_error = envelope.get("error")
        if isinstance(raw_error, dict):
            message = str(raw_error.get("message", "Unknown API error"))
            code = _optional_string(raw_error.get("code"))
            request_id = _optional_string(raw_error.get("requestId")) or response.headers.get(
                "X-Request-ID"
            )
            details = raw_error.get("details")
            if not isinstance(details, dict):
                details = None
            retryable = bool(raw_error.get("retryable", False))
            field_errors = _field_errors(raw_error.get("fieldErrors"))
        else:
            details = envelope or None
            message = str(raw_error) if raw_error is not None else "Unknown API error"
            code = None
            request_id = response.headers.get("X-Request-ID")
            retryable = response.status_code in {429, 503}
            field_errors = ()
        error_type = _ERROR_CODES.get(code or "", _ERRORS.get(response.status_code, HTTPError))

        if error_type is RateLimited:
            raise RateLimited(
                response.status_code,
                message,
                details,
                request_id,
                HTTPTransport._parse_retry_after(response, details),
                code=code,
                retryable=retryable,
                field_errors=field_errors,
            )
        raise error_type(
            response.status_code,
            message,
            details,
            request_id,
            code,
            retryable,
            field_errors,
        )

    @staticmethod
    def _result(response: httpx.Response, payload: dict[str, Any] | None) -> HTTPResult:
        return HTTPResult(
            payload=payload,
            status_code=response.status_code,
            request_id=response.headers.get("X-Request-ID"),
            api_version=response.headers.get("X-VoiceRoute-API-Version"),
            etag=response.headers.get("ETag"),
            rate_limit=HTTPTransport._rate_limit_metadata(response),
        )

    @staticmethod
    def _rate_limit_metadata(response: httpx.Response) -> RateLimitMetadata:
        return RateLimitMetadata(
            limit=_optional_int(response.headers.get("X-RateLimit-Limit")),
            remaining=_optional_int(response.headers.get("X-RateLimit-Remaining")),
            reset_after=_optional_float(response.headers.get("X-RateLimit-Reset-After")),
            bucket=response.headers.get("X-RateLimit-Bucket"),
            scope=response.headers.get("X-RateLimit-Scope"),
        )

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
    def _parse_retry_after(
        response: httpx.Response, details: Mapping[str, Any] | None = None
    ) -> float | None:
        header = _optional_float(response.headers.get("Retry-After"))
        if header is not None:
            return header
        if details is None:
            try:
                payload = response.json()
            except ValueError:
                payload = None
            raw_error = payload.get("error") if isinstance(payload, dict) else None
            raw_details = raw_error.get("details") if isinstance(raw_error, dict) else None
            details = raw_details if isinstance(raw_details, dict) else None
        value = details.get("retryAfterMs") if details is not None else None
        milliseconds = _optional_float(str(value)) if value is not None else None
        return milliseconds / 1000 if milliseconds is not None else None


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _optional_float(value: str | None) -> float | None:
    try:
        return max(0.0, float(value)) if value is not None else None
    except ValueError:
        return None


def _field_errors(value: object) -> tuple[FieldError, ...]:
    if not isinstance(value, list):
        return ()
    result: list[FieldError] = []
    for item in value:
        if not isinstance(item, dict) or "field" not in item or "code" not in item:
            continue
        result.append(
            FieldError(
                field=str(item["field"]),
                code=str(item["code"]),
                message=_optional_string(item.get("message")),
            )
        )
    return tuple(result)
