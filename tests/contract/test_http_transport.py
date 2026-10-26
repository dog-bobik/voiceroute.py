from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from voiceroute.errors import (
    ClientClosedError,
    RateLimited,
    ResourceVersionConflict,
    TransportError,
    Unauthorized,
)
from voiceroute.transport import HTTPTransport, RateLimitMetadata


@respx.mock
async def test_transport_sends_bot_authorization() -> None:
    route = respx.get("https://dev.voiceroute.cc/api/bots/@me").mock(
        return_value=httpx.Response(200, json={"applicationId": "app", "user": {}})
    )
    transport = HTTPTransport(
        token="vrb_secret",
        base_url="https://dev.voiceroute.cc",
        timeout=1,
    )

    await transport.request("GET", "/api/bots/@me")
    await transport.close()

    assert route.calls[0].request.headers["Authorization"] == "Bot vrb_secret"


@respx.mock
async def test_transport_maps_unauthorized_response() -> None:
    respx.get("https://voiceroute.cc/api/bots/@me").mock(
        return_value=httpx.Response(401, json={"error": "revoked"})
    )
    transport = HTTPTransport(
        token="vrb_secret",
        base_url="https://voiceroute.cc",
        timeout=1,
        max_attempts=1,
    )

    with pytest.raises(Unauthorized, match="401"):
        await transport.request("GET", "/api/bots/@me")
    await transport.close()


@respx.mock
async def test_transport_preserves_retry_after() -> None:
    respx.get("https://voiceroute.cc/api/communities").mock(
        return_value=httpx.Response(
            429,
            headers={"Retry-After": "1.5"},
            json={"error": "slow down"},
        )
    )
    transport = HTTPTransport(
        token="vrb_secret",
        base_url="https://voiceroute.cc",
        timeout=1,
        max_attempts=1,
    )

    with pytest.raises(RateLimited) as captured:
        await transport.request("GET", "/api/communities")
    await transport.close()

    assert captured.value.retry_after == 1.5


@respx.mock
async def test_transport_retries_rate_limit_with_retry_after() -> None:
    route = respx.get("https://voiceroute.cc/api/communities").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "2"}, json={"error": "slow down"}),
            httpx.Response(200, json={"items": []}),
        ]
    )
    transport = HTTPTransport(token="vrb_secret", base_url="https://voiceroute.cc", timeout=1)

    with patch("voiceroute.transport.http.asyncio.sleep", new=AsyncMock()) as sleep:
        payload = await transport.request("GET", "/api/communities")
    await transport.close()

    assert payload == {"items": []}
    assert route.call_count == 2
    sleep.assert_awaited_once_with(2.0)


@respx.mock
async def test_transport_does_not_retry_unsafe_network_failure() -> None:
    route = respx.post("https://voiceroute.cc/api/action").mock(
        side_effect=httpx.ConnectError("connection lost")
    )
    transport = HTTPTransport(token="vrb_secret", base_url="https://voiceroute.cc", timeout=1)

    with pytest.raises(TransportError):
        await transport.request("POST", "/api/action", json={"value": 1})
    await transport.close()

    assert route.call_count == 1


@respx.mock
async def test_transport_rejects_invalid_success_payload() -> None:
    respx.get("https://voiceroute.cc/api/bots/@me").mock(
        return_value=httpx.Response(200, text="not json")
    )
    transport = HTTPTransport(token="vrb_secret", base_url="https://voiceroute.cc", timeout=1)

    with pytest.raises(TransportError, match="invalid JSON"):
        await transport.request("GET", "/api/bots/@me")
    await transport.close()


async def test_transport_cannot_be_reused_after_close() -> None:
    transport = HTTPTransport(token="vrb_secret", base_url="https://voiceroute.cc", timeout=1)
    await transport.close()

    with pytest.raises(ClientClosedError):
        await transport.request("GET", "/api/bots/@me")


@respx.mock
async def test_transport_omits_none_query_parameters() -> None:
    route = respx.get("https://voiceroute.cc/api/communities").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    transport = HTTPTransport(token="vrb_secret", base_url="https://voiceroute.cc", timeout=1)

    await transport.request(
        "GET",
        "/api/communities",
        params={"after": None, "limit": 50},
    )
    await transport.close()

    assert str(route.calls[0].request.url) == "https://voiceroute.cc/api/communities?limit=50"


@respx.mock
async def test_transport_parses_v1_error_envelope() -> None:
    respx.patch("https://voiceroute.cc/api/v1/resource").mock(
        return_value=httpx.Response(
            409,
            headers={"X-Request-ID": "header-request"},
            json={
                "error": {
                    "code": "RESOURCE_VERSION_CONFLICT",
                    "message": "Refresh before saving",
                    "requestId": "body-request",
                    "retryable": False,
                    "details": {"currentETag": '"platform-2"'},
                    "fieldErrors": [{"field": "name", "code": "INVALID"}],
                }
            },
        )
    )
    transport = HTTPTransport(token="vrb_secret", base_url="https://voiceroute.cc", timeout=1)

    with pytest.raises(ResourceVersionConflict) as captured:
        await transport.request(
            "PATCH",
            "/api/v1/resource",
            json={"name": "new"},
            if_match='"platform-1"',
            idempotency_key="018f47a0-d4c0-7c73-a7cc-123456789abc",
        )
    await transport.close()

    assert captured.value.code == "RESOURCE_VERSION_CONFLICT"
    assert captured.value.request_id == "body-request"
    assert captured.value.details == {"currentETag": '"platform-2"'}
    assert captured.value.field_errors[0].field == "name"


@respx.mock
async def test_transport_exposes_v1_response_metadata() -> None:
    route = respx.patch("https://voiceroute.cc/api/v1/resource").mock(
        return_value=httpx.Response(
            200,
            headers={
                "X-Request-ID": "request-id",
                "X-VoiceRoute-API-Version": "1",
                "ETag": '"resource-2"',
                "X-RateLimit-Limit": "50",
                "X-RateLimit-Remaining": "49",
                "X-RateLimit-Reset-After": "0.5",
                "X-RateLimit-Bucket": "bot-global",
                "X-RateLimit-Scope": "application",
            },
            json={"version": "2"},
        )
    )
    transport = HTTPTransport(token="vrb_secret", base_url="https://voiceroute.cc", timeout=1)

    result = await transport.request_with_response(
        "PATCH",
        "/api/v1/resource",
        json={"name": "new"},
        if_match='"resource-1"',
        idempotency_key="018f47a0-d4c0-7c73-a7cc-123456789abc",
    )
    await transport.close()

    assert route.calls.last.request.headers["If-Match"] == '"resource-1"'
    assert route.calls.last.request.headers["Idempotency-Key"].startswith("018f47a0")
    assert result.etag == '"resource-2"'
    assert result.api_version == "1"
    assert result.rate_limit == RateLimitMetadata(50, 49, 0.5, "bot-global", "application")
