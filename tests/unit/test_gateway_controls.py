from types import SimpleNamespace
from typing import Any

import pytest

from voiceroute import Activity, Game, Intent, Intents, Presence, Status
from voiceroute.errors import IntentNotEnabled, PrivilegedIntentRequired
from voiceroute.gateway import GatewayClient
from voiceroute.models import GatewayDiscovery, GatewaySessionStartLimit


def test_intents_default_and_all_are_deterministic() -> None:
    defaults = Intents.default()

    assert Intent.MESSAGES in defaults
    assert Intent.MEMBERS not in defaults
    assert set(Intents.all().values) == {intent.value for intent in Intent}


def test_presence_validates_protocol_limits() -> None:
    assert Presence(Status.ONLINE, (Game("/help"),)).to_dict() == {
        "status": "online",
        "activities": [{"type": "PLAYING", "name": "/help"}],
    }
    with pytest.raises(ValueError, match="four activities"):
        Presence(Status.ONLINE, tuple(Activity(str(index)) for index in range(5)))
    with pytest.raises(ValueError, match="invisible"):
        Presence(Status.INVISIBLE, (Game("hidden"),))


class PrivilegedPlatform:
    async def gateway(self) -> GatewayDiscovery:
        return GatewayDiscovery(
            "wss://voiceroute.cc/api/v1/gateway/socket?v=1&encoding=json",
            1,
            GatewaySessionStartLimit(1000, 999, 0, 1),
        )

    async def capabilities(self) -> Any:
        return SimpleNamespace(intents={"members": SimpleNamespace(privileged=True)})

    async def current_application(self) -> Any:
        return SimpleNamespace(requested_intents=("members",), approved_intents=())


async def test_gateway_rejects_unapproved_privileged_intent() -> None:
    client = GatewayClient(
        token="vrb_test",
        platform_api=PrivilegedPlatform(),  # type: ignore[arg-type]
        base_url="https://voiceroute.cc",
        intents=Intents(members=True),
    )

    async def ignore(event: Any) -> None:
        return None

    with pytest.raises(PrivilegedIntentRequired) as captured:
        await client.run_once(ignore)
    assert captured.value.intents == ("members",)


async def test_gateway_rejects_intent_not_enabled_for_application() -> None:
    platform = PrivilegedPlatform()
    platform.current_application = lambda: _application(())  # type: ignore[method-assign]
    client = GatewayClient(
        token="vrb_test",
        platform_api=platform,  # type: ignore[arg-type]
        base_url="https://voiceroute.cc",
        intents=Intents(members=True),
    )

    async def ignore(event: Any) -> None:
        return None

    with pytest.raises(IntentNotEnabled) as captured:
        await client.run_once(ignore)
    assert captured.value.intents == ("members",)


async def _application(requested: tuple[str, ...]) -> Any:
    return SimpleNamespace(requested_intents=requested, approved_intents=())
