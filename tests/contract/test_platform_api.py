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


@respx.mock
async def test_status_specs_and_explicit_refresh() -> None:
    capabilities_route = respx.get("https://voiceroute.cc/api/v1/capabilities").mock(
        return_value=httpx.Response(200, json=CAPABILITIES)
    )
    status_route = respx.get("https://voiceroute.cc/api/v1/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "degraded",
                "checkedAt": "2026-10-27T00:00:00Z",
                "components": {
                    "api": "operational",
                    "eventDelivery": "degraded",
                    "voice": "unknown",
                },
                "incidents": [],
            },
        )
    )
    respx.get("https://voiceroute.cc/api/v1/openapi.json").mock(
        return_value=httpx.Response(200, json={"openapi": "3.1.0"})
    )
    respx.get("https://voiceroute.cc/api/v1/asyncapi.json").mock(
        return_value=httpx.Response(200, json={"asyncapi": "3.0.0"})
    )
    transport = HTTPTransport(token="vrb_test", base_url="https://voiceroute.cc", timeout=1)
    api = PlatformAPI(transport)

    first = await api.status()
    second = await api.status()
    assert first is second and first.degraded
    assert first.component_available("api")
    assert not first.component_available("voice")
    assert (await api.openapi())["openapi"] == "3.1.0"
    assert (await api.asyncapi())["asyncapi"] == "3.0.0"

    await api.refresh()
    await transport.close()
    assert capabilities_route.call_count == 1
    assert status_route.call_count == 2


@respx.mock
async def test_safe_diagnostics_reports_unapproved_intents_without_token() -> None:
    respx.get("https://voiceroute.cc/api/v1/capabilities").mock(
        return_value=httpx.Response(200, json=CAPABILITIES)
    )
    respx.get("https://voiceroute.cc/api/v1/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "operational",
                "checkedAt": "2026-10-27T00:00:00Z",
                "components": {},
                "incidents": [],
            },
        )
    )
    respx.get("https://voiceroute.cc/api/v1/applications/@me").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "app",
                "name": "Bot",
                "description": "",
                "public": False,
                "bot": {"id": "1", "username": "bot", "displayName": "Bot"},
                "requestedIntents": ["messages", "messageContent"],
                "approvedIntents": ["messages"],
            },
        )
    )
    transport = HTTPTransport(token="vrb_secret", base_url="https://voiceroute.cc", timeout=1)
    diagnostics = await PlatformAPI(transport).diagnostics()
    await transport.close()

    assert diagnostics.unavailable_intents == ("messageContent",)
    assert "vrb_secret" not in repr(diagnostics)
