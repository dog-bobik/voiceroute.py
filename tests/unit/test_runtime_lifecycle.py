import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from voiceroute import (
    Bot,
    BotAlreadyRunning,
    BotClosed,
    BotIdentity,
    Forbidden,
    RuntimeState,
    User,
)
from voiceroute.events import ChannelTarget, EventDelivery, StreamCheckpoint


class BlockingTransport:
    def __init__(self) -> None:
        self.started = asyncio.Event()

    def stream_key(self, target: ChannelTarget) -> str:
        return f"blocking:{target.community_id}:{target.channel_id}"

    async def listen(
        self,
        target: ChannelTarget,
        *,
        checkpoint: StreamCheckpoint | None,
        initial_after_seq: str | None,
    ) -> AsyncIterator[EventDelivery]:
        self.started.set()
        await asyncio.Future()
        if False:
            yield


class LifecycleBot(Bot):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.lifecycle: list[str] = []

    async def setup_hook(self) -> None:
        self.lifecycle.append("setup")


def identity() -> BotIdentity:
    return BotIdentity(User(42, "bot", "Bot", bot=True), "application")


async def test_start_stop_runs_lifecycle_and_cancels_consumers() -> None:
    transport = BlockingTransport()
    bot = LifecycleBot(
        token="vrb_secret",
        community_id="community",
        channel_id="channel",
        event_transport=transport,
    )
    bot.client.bots.get_current = AsyncMock(return_value=identity())
    bot.client.close = AsyncMock()

    @bot.event
    async def on_connect() -> None:
        bot.lifecycle.append("connect")

    @bot.event
    async def on_ready() -> None:
        bot.lifecycle.append("ready")

    @bot.event
    async def on_shutdown() -> None:
        bot.lifecycle.append("shutdown")

    running = asyncio.create_task(bot.start())
    await bot.wait_until_ready()
    await transport.started.wait()

    assert bot.state is RuntimeState.RUNNING
    assert bot.is_ready()
    await bot.stop()
    await running

    assert bot.lifecycle == ["setup", "connect", "ready", "shutdown"]
    assert bot.is_closed()
    assert not bot.is_ready()
    bot.client.close.assert_awaited_once()


async def test_stop_is_idempotent_and_closed_bot_cannot_restart() -> None:
    bot = Bot(token="vrb_secret")
    bot.client.close = AsyncMock()

    await bot.stop()
    await bot.stop()

    assert bot.state is RuntimeState.CLOSED
    bot.client.close.assert_awaited_once()
    with pytest.raises(BotClosed):
        await bot.start()
    with pytest.raises(BotClosed):
        await bot.wait_until_ready()


async def test_start_rejects_concurrent_start() -> None:
    transport = BlockingTransport()
    bot = Bot(
        token="vrb_secret",
        community_id="community",
        channel_id="channel",
        event_transport=transport,
    )
    bot.client.bots.get_current = AsyncMock(return_value=identity())
    running = asyncio.create_task(bot.start())
    await bot.wait_until_ready()

    with pytest.raises(BotAlreadyRunning):
        await bot.start()

    await bot.stop()
    await running


async def test_consumer_supervisor_restarts_with_bounded_backoff() -> None:
    bot = Bot(token="vrb_secret", max_consumer_backoff=2)
    target = ChannelTarget("community", "channel")
    bot._consume_channel = AsyncMock(  # type: ignore[method-assign]
        side_effect=[RuntimeError("stream failed"), RuntimeError("again"), None]
    )
    lifecycle: list[tuple[str, float | str]] = []

    @bot.event
    async def on_disconnect(event_target: ChannelTarget, error: Exception) -> None:
        lifecycle.append(("disconnect", str(error)))

    @bot.event
    async def on_reconnect(event_target: ChannelTarget, delay: float) -> None:
        lifecycle.append(("reconnect", delay))

    @bot.event
    async def on_resumed(event_target: ChannelTarget) -> None:
        lifecycle.append(("resumed", event_target.channel_id))

    with patch("voiceroute.bot.asyncio.sleep", new=AsyncMock()) as sleep:
        await bot._supervise_channel(target)

    assert sleep.await_args_list[0].args == (1.0,)
    assert sleep.await_args_list[1].args == (2.0,)
    assert lifecycle == [
        ("disconnect", "stream failed"),
        ("reconnect", 1.0),
        ("resumed", "channel"),
        ("disconnect", "again"),
        ("reconnect", 2.0),
        ("resumed", "channel"),
    ]
    await bot.close()


async def test_consumer_cancellation_is_not_retried() -> None:
    bot = Bot(token="vrb_secret")
    bot._consume_channel = AsyncMock(side_effect=asyncio.CancelledError)  # type: ignore[method-assign]

    with pytest.raises(asyncio.CancelledError):
        await bot._supervise_channel(ChannelTarget("community", "channel"))
    await bot.close()


async def test_forbidden_consumer_is_reported_without_retry() -> None:
    bot = Bot(token="vrb_secret")
    error = Forbidden(403, "privileged intent required")
    bot._consume_channel = AsyncMock(side_effect=error)  # type: ignore[method-assign]
    target = ChannelTarget("community", "channel")
    unavailable = AsyncMock()
    bot.add_listener(unavailable, "on_stream_unavailable")

    with patch("voiceroute.bot.asyncio.sleep", new=AsyncMock()) as sleep:
        await bot._supervise_channel(target)

    unavailable.assert_awaited_once_with(target, error)
    sleep.assert_not_awaited()
    assert bot._consume_channel.await_count == 1
    await bot.close()


def test_consumer_backoff_must_be_positive() -> None:
    with pytest.raises(ValueError, match="backoff"):
        Bot(token="vrb_secret", max_consumer_backoff=0)
