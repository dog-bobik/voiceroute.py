import httpx
import pytest
import respx

from voiceroute import VoiceRouteClient


@respx.mock
async def test_get_and_complete_mini_app_action_with_state() -> None:
    state_route = respx.get(
        "https://voiceroute.cc/api/v1/applications/app/mini-app/instances/instance/state"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"instanceId": "instance", "version": "7", "state": {"playing": True}},
        )
    )
    complete_route = respx.post(
        "https://voiceroute.cc/api/v1/applications/app/mini-app/actions/action/complete"
    ).mock(return_value=httpx.Response(200, json={"status": "COMPLETED"}))

    async with VoiceRouteClient(token="vrb_test") as client:
        state = await client.mini_apps.get_state("app", "instance")
        result = await client.mini_apps.complete_action(
            "app",
            "action",
            state={"playing": False},
            version=state.version,
            idempotency_key="action",
        )

    assert state.version == "7"
    assert state.state == {"playing": True}
    assert result == {"status": "COMPLETED"}
    assert state_route.called
    request = complete_route.calls.last.request
    assert request.headers["If-Match"] == '"state-7"'
    assert request.headers["Idempotency-Key"] == "action"
    assert request.content == b'{"result":null,"state":{"playing":false}}'


async def test_complete_mini_app_action_requires_state_version_pair() -> None:
    async with VoiceRouteClient(token="vrb_test") as client:
        with pytest.raises(ValueError, match="provided together"):
            await client.mini_apps.complete_action("app", "action", state={})
