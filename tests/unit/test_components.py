from unittest.mock import AsyncMock

from voiceroute import ComponentRouter


async def test_component_router_signs_routes_and_rejects_tampering() -> None:
    router = ComponentRouter("0123456789abcdef")
    callback = AsyncMock()
    router.register("refresh", callback)
    custom_id = router.custom_id("refresh", "page-2")
    context = object()

    assert await router.dispatch(context, custom_id) is True  # type: ignore[arg-type]
    callback.assert_awaited_once_with(context, "page-2")
    assert await router.dispatch(context, custom_id + "x") is False  # type: ignore[arg-type]
