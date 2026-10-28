from types import SimpleNamespace
from typing import Any

import pytest

from voiceroute import Activity, Capabilities, Capability, Game, Presence, Status
from voiceroute.errors import InstallationGrantRequired
from voiceroute.gateway import GatewayClient
from voiceroute.models import GatewayDiscovery, GatewaySessionStartLimit


def test_capabilities_default_and_all_are_deterministic() -> None:
    defaults = Capabilities.default()

    assert len(defaults) == 0
    assert set(Capabilities.all().values) == {capability.value for capability in Capability}


def test_presence_validates_protocol_limits() -> None:
    assert Presence(Status.ONLINE, (Game("/help"),)).to_dict() == {
        "status": "online",
        "activities": [{"type": "PLAYING", "name": "/help"}],
    }
    with pytest.raises(ValueError, match="four activities"):
        Presence(Status.ONLINE, tuple(Activity(str(index)) for index in range(5)))
    with pytest.raises(ValueError, match="invisible"):
        Presence(Status.INVISIBLE, (Game("hidden"),))


class InstallationPlatform:
    async def gateway(self) -> GatewayDiscovery:
        return GatewayDiscovery(
            "wss://voiceroute.cc/api/v1/gateway/socket?v=1&encoding=json",
            1,
            GatewaySessionStartLimit(1000, 999, 0, 1),
        )

    async def capabilities(self) -> Any:
        return SimpleNamespace(event_capabilities=("members",))

    async def current_application(self) -> Any:
        return SimpleNamespace(granted_capabilities=())


async def test_gateway_rejects_missing_installation_grant() -> None:
    client = GatewayClient(
        token="vrb_test",
        platform_api=InstallationPlatform(),  # type: ignore[arg-type]
        base_url="https://voiceroute.cc",
        capabilities=Capabilities(members=True),
    )

    async def ignore(event: Any) -> None:
        return None

    with pytest.raises(InstallationGrantRequired) as captured:
        await client.run_once(ignore)
    assert captured.value.intents == ("members",)


async def test_gateway_rejects_capability_not_granted_for_application() -> None:
    platform = InstallationPlatform()
    platform.current_application = lambda: _application(())  # type: ignore[method-assign]
    client = GatewayClient(
        token="vrb_test",
        platform_api=platform,  # type: ignore[arg-type]
        base_url="https://voiceroute.cc",
        capabilities=Capabilities(members=True),
    )

    async def ignore(event: Any) -> None:
        return None

    with pytest.raises(InstallationGrantRequired) as captured:
        await client.run_once(ignore)
    assert captured.value.intents == ("members",)


async def _application(granted: tuple[str, ...]) -> Any:
    return SimpleNamespace(granted_capabilities=granted)
