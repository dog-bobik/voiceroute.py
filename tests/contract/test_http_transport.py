import httpx
import pytest
import respx

from voiceroute.errors import ClientClosedError, RateLimited, TransportError, Unauthorized
from voiceroute.transport import HTTPTransport


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
    transport = HTTPTransport(token="vrb_secret", base_url="https://voiceroute.cc", timeout=1)

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
    transport = HTTPTransport(token="vrb_secret", base_url="https://voiceroute.cc", timeout=1)

    with pytest.raises(RateLimited) as captured:
        await transport.request("GET", "/api/communities")
    await transport.close()

    assert captured.value.retry_after == 1.5


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
