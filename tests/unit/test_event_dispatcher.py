import asyncio

import pytest

from voiceroute import Bot, EventDispatcher, PlatformEvent


def event(
    name: str = "MEMBER_JOINED",
    *,
    delivery_id: str = "00000000-0000-4000-8000-000000000001",
) -> PlatformEvent:
    return PlatformEvent.from_gateway_frame(
        {
            "op": 0,
            "event": name,
            "sequence": "2",
            "deliveryId": delivery_id,
            "data": {"communityId": "community", "userId": "42"},
        }
    )


async def test_dispatcher_routes_named_and_raw_listeners_once() -> None:
    dispatcher = EventDispatcher()
    named: list[PlatformEvent] = []
    raw: list[PlatformEvent] = []

    async def on_member_joined(item: PlatformEvent) -> None:
        named.append(item)

    async def on_raw(item: PlatformEvent) -> None:
        raw.append(item)

    dispatcher.add_listener(on_member_joined, "on_member_joined")
    dispatcher.add_listener(on_raw)

    assert await dispatcher.dispatch(event()) is True
    assert await dispatcher.dispatch(event()) is False
    assert len(named) == len(raw) == 1


async def test_dispatcher_wait_for_applies_filter() -> None:
    dispatcher = EventDispatcher()
    waiting = asyncio.create_task(
        dispatcher.wait_for(
            "member_joined",
            check=lambda item: item.data.get("userId") == "42",
            timeout=1,
        )
    )
    await asyncio.sleep(0)

    await dispatcher.dispatch(event())

    assert await waiting == event()


async def test_dispatcher_does_not_ack_unhandled_listener_error() -> None:
    dispatcher = EventDispatcher()

    async def fail(item: PlatformEvent) -> None:
        raise RuntimeError("handler failed")

    dispatcher.add_listener(fail, "MEMBER_JOINED")
    with pytest.raises(RuntimeError, match="handler failed"):
        await dispatcher.dispatch(event())
    with pytest.raises(RuntimeError, match="handler failed"):
        await dispatcher.dispatch(event())


async def test_bot_exposes_known_and_unknown_gateway_events() -> None:
    bot = Bot(token="vrb_test", event_transport="gateway")
    known: list[PlatformEvent] = []
    unknown: list[PlatformEvent] = []

    @bot.event
    async def on_member_joined(item: PlatformEvent) -> None:
        known.append(item)

    @bot.event
    async def on_unknown_event(item: PlatformEvent) -> None:
        unknown.append(item)

    await bot.dispatcher.dispatch(event())
    await bot.dispatcher.dispatch(event("BRAND_NEW_EVENT", delivery_id="new"))
    await bot.client.close()

    assert [item.name for item in known] == ["MEMBER_JOINED"]
    assert [item.name for item in unknown] == ["BRAND_NEW_EVENT"]


def test_gateway_keeps_legacy_message_stream_only_when_needed() -> None:
    bot = Bot(token="vrb_test", event_transport="gateway")
    assert bot._needs_legacy_message_streams() is False

    @bot.command()
    async def ping(ctx: object) -> None:
        return None

    assert bot._needs_legacy_message_streams() is True
