import httpx
import pytest
import respx

from voiceroute import APIVersion, VoiceRouteClient
from voiceroute.api import PlatformAPI
from voiceroute.errors import FeatureUnavailable
from voiceroute.transport import HTTPTransport

CAPABILITIES = {
    "apiVersion": "1",
    "maturity": "preview",
    "stage": "gateway",
    "environment": {"mode": "development"},
    "gateway": {
        "encoding": ["json"],
        "compression": False,
        "shardCounts": [1, 2],
        "replayWindowMs": 300_000,
        "maxSessionsPerApplication": 2,
        "heartbeatIntervalMs": 30_000,
        "maxClientFrameBytes": 16_384,
    },
    "features": {"gateway": True, "voice": False},
    "events": ["READY", "MESSAGE_CREATE"],
    "intents": {"MESSAGES": {"privileged": False}},
    "legacy": {"rest": True, "sse": True, "sunsetAt": None},
}


@respx.mock
async def test_capabilities_are_typed_and_cached() -> None:
    route = respx.get("https://voiceroute.cc/api/v1/capabilities").mock(
        return_value=httpx.Response(200, json=CAPABILITIES)
    )
    transport = HTTPTransport(token="vrb_test", base_url="https://voiceroute.cc", timeout=1)
    api = PlatformAPI(transport)

    first = await api.capabilities()
    second = await api.capabilities()
    await transport.close()

    assert first is second
    assert first.gateway.shard_counts == (1, 2)
    assert first.intents["MESSAGES"].privileged is False
    assert first.supports("gateway") is True
    assert route.call_count == 1


@respx.mock
async def test_require_rejects_disabled_feature() -> None:
    respx.get("https://voiceroute.cc/api/v1/capabilities").mock(
        return_value=httpx.Response(200, json=CAPABILITIES)
    )
    transport = HTTPTransport(token="vrb_test", base_url="https://voiceroute.cc", timeout=1)
    api = PlatformAPI(transport)

    with pytest.raises(FeatureUnavailable, match="voice"):
        await api.require("voice")
    await transport.close()


@respx.mock
async def test_current_application_parses_bot_identity() -> None:
    respx.get("https://voiceroute.cc/api/v1/applications/@me").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "app-1",
                "name": "Helper",
                "description": "Example",
                "public": False,
                "permissions": ["SEND_MESSAGES"],
                "bot": {
                    "id": "9007199254740993",
                    "username": "helper",
                    "displayName": "Helper Bot",
                    "bot": True,
                },
                "requestedIntents": ["MESSAGES"],
                "approvedIntents": ["MESSAGES"],
            },
        )
    )
    transport = HTTPTransport(token="vrb_test", base_url="https://voiceroute.cc", timeout=1)
    application = await PlatformAPI(transport).current_application()
    await transport.close()

    assert application.bot.id == "9007199254740993"
    assert application.approved_intents == ("MESSAGES",)


@respx.mock
async def test_client_resolves_auto_api_version() -> None:
    respx.get("https://voiceroute.cc/api/v1/capabilities").mock(
        return_value=httpx.Response(200, json=CAPABILITIES)
    )
    client = VoiceRouteClient(token="vrb_test")

    assert await client.resolve_api_version() is APIVersion.V1
    await client.close()


async def test_client_preserves_explicit_legacy_mode() -> None:
    client = VoiceRouteClient(token="vrb_test", api_version="legacy")

    assert await client.resolve_api_version() is APIVersion.LEGACY
    await client.close()
