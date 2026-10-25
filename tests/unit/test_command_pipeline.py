import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from voiceroute import (
    BucketType,
    CheckFailure,
    Command,
    CommandOnCooldown,
    CommandPipeline,
    Context,
    MaxConcurrencyReached,
    check,
    cooldown,
    max_concurrency,
)
from voiceroute.models import Message, User


def context(*, user_id: int = 7, channel_id: str = "channel") -> Context:
    return Context(
        Message(
            seq="17",
            community_id="community",
            channel_id=channel_id,
            body="!work",
            author=User(user_id, f"member-{user_id}", "Member"),
        ),
        "work",
        (),
        AsyncMock(),
    )


async def test_middleware_wraps_command_in_registration_order() -> None:
    order: list[str] = []

    async def callback(ctx: Context) -> None:
        order.append("command")

    async def first(ctx: Context, call_next) -> None:
        order.append("first:before")
        await call_next()
        order.append("first:after")

    async def second(ctx: Context, call_next) -> None:
        order.append("second:before")
        await call_next()
        order.append("second:after")

    pipeline = CommandPipeline()
    pipeline.add_middleware(first)
    pipeline.add_middleware(second)
    await pipeline.invoke(Command.from_callback(callback), context(), ())

    assert order == [
        "first:before",
        "second:before",
        "command",
        "second:after",
        "first:after",
    ]


async def test_middleware_can_stop_pipeline() -> None:
    callback = AsyncMock()

    async def stop(ctx: Context, call_next) -> None:
        return None

    pipeline = CommandPipeline()
    pipeline.add_middleware(stop)
    await pipeline.invoke(Command.from_callback(callback), context(), ())

    callback.assert_not_awaited()


async def test_middleware_cannot_call_next_twice() -> None:
    async def callback(ctx: Context) -> None:
        pass

    async def broken(ctx: Context, call_next) -> None:
        await call_next()
        await call_next()

    pipeline = CommandPipeline()
    pipeline.add_middleware(broken)

    with pytest.raises(RuntimeError, match="more than once"):
        await pipeline.invoke(Command.from_callback(callback), context(), ())


async def test_sync_and_async_checks_run_before_command() -> None:
    called = False

    async def async_allowed(ctx: Context) -> bool:
        return True

    def denied(ctx: Context) -> bool:
        return False

    @check(async_allowed)
    @check(denied)
    async def callback(ctx: Context) -> None:
        nonlocal called
        called = True

    with pytest.raises(CheckFailure) as failure:
        await CommandPipeline().invoke(Command.from_callback(callback), context(), ())

    assert failure.value.check == "denied"
    assert called is False


async def test_cooldown_is_partitioned_by_bucket() -> None:
    @cooldown(1, 10, bucket=BucketType.USER)
    async def callback(ctx: Context) -> None:
        pass

    command = Command.from_callback(callback)
    pipeline = CommandPipeline()
    with patch("voiceroute.commands.pipeline.time.monotonic", return_value=100.0):
        await pipeline.invoke(command, context(user_id=1), ())
        await pipeline.invoke(command, context(user_id=2), ())
        with pytest.raises(CommandOnCooldown) as limited:
            await pipeline.invoke(command, context(user_id=1), ())

    assert limited.value.retry_after == pytest.approx(10.0)


async def test_cooldown_expires() -> None:
    @cooldown(1, 10)
    async def callback(ctx: Context) -> None:
        pass

    command = Command.from_callback(callback)
    pipeline = CommandPipeline()
    with patch(
        "voiceroute.commands.pipeline.time.monotonic",
        side_effect=[100.0, 111.0],
    ):
        await pipeline.invoke(command, context(), ())
        await pipeline.invoke(command, context(), ())


async def test_concurrency_limit_is_released_after_completion() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    @max_concurrency(1, bucket=BucketType.CHANNEL)
    async def callback(ctx: Context) -> None:
        entered.set()
        await release.wait()

    command = Command.from_callback(callback)
    pipeline = CommandPipeline()
    first = asyncio.create_task(pipeline.invoke(command, context(), ()))
    await entered.wait()

    with pytest.raises(MaxConcurrencyReached):
        await pipeline.invoke(command, context(), ())

    release.set()
    await first

    release.clear()
    release.set()
    await pipeline.invoke(command, context(), ())


def test_pipeline_configuration_is_validated() -> None:
    with pytest.raises(ValueError, match="rate"):
        cooldown(0, 1)
    with pytest.raises(ValueError, match="period"):
        cooldown(1, 0)
    with pytest.raises(ValueError, match="concurrency"):
        max_concurrency(0)

    with pytest.raises(TypeError, match="async"):
        CommandPipeline().add_middleware(lambda ctx, call_next: None)  # type: ignore[arg-type]
