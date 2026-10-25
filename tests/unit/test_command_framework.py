from unittest.mock import AsyncMock

import pytest

from voiceroute import (
    BadArgument,
    Bot,
    Command,
    CommandNotFound,
    CommandParsingError,
    CommandRegistry,
    Context,
    MissingRequiredArgument,
    PrefixCommandAdapter,
    TooManyArguments,
)
from voiceroute.events import MessageUpserted
from voiceroute.models import Message, User


def incoming_message(body: str) -> Message:
    return Message(
        seq="17",
        community_id="community-id",
        channel_id="channel-id",
        body=body,
        author=User(7, "member", "Member"),
    )


async def test_command_metadata_uses_docstring_and_alias() -> None:
    async def ping(context: Context) -> None:
        """Measure bot latency."""

    command = Command.from_callback(ping, aliases=("p",), usage="ping")

    assert command.name == "ping"
    assert command.aliases == (("p",),)
    assert command.description == "Measure bot latency."
    assert command.usage == "ping"


async def test_registry_resolves_longest_group_and_leaf_alias() -> None:
    async def ban(context: Context, user_id: int) -> None:
        pass

    command = Command.from_callback(ban, name="admin ban", aliases=("block",))
    registry = CommandRegistry()
    registry.add(command)

    resolved, invocation = registry.resolve(("admin", "block", "42"))

    assert resolved is command
    assert invocation.path == ("admin", "ban")
    assert invocation.arguments == ("42",)
    assert registry.get("admin block") is command


async def test_registry_rejects_duplicate_alias() -> None:
    async def first(context: Context) -> None:
        pass

    async def second(context: Context) -> None:
        pass

    registry = CommandRegistry()
    registry.add(Command.from_callback(first, aliases=("shared",)))

    with pytest.raises(ValueError, match="already registered"):
        registry.add(Command.from_callback(second, aliases=("shared",)))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("true", True), ("YES", True), ("0", False), ("off", False)],
)
async def test_typed_command_converts_arguments(raw: str, expected: bool) -> None:
    captured: list[tuple[int, float, bool, str | None]] = []

    async def configure(
        context: Context,
        count: int,
        ratio: float,
        enabled: bool,
        label: str | None = None,
    ) -> None:
        captured.append((count, ratio, enabled, label))

    command = Command.from_callback(configure)
    context = Context(incoming_message("!configure"), "configure", (), AsyncMock())
    await command.invoke(context, ("4", "1.5", raw))

    assert captured == [(4, 1.5, expected, None)]


async def test_variadic_arguments_are_converted() -> None:
    captured: list[tuple[int, ...]] = []

    async def add(context: Context, *values: int) -> None:
        captured.append(values)

    command = Command.from_callback(add)
    context = Context(incoming_message("!add"), "add", (), AsyncMock())
    await command.invoke(context, ("1", "2", "3"))

    assert captured == [(1, 2, 3)]


async def test_argument_errors_are_specific() -> None:
    async def resize(context: Context, width: int, height: int = 10) -> None:
        pass

    command = Command.from_callback(resize)

    with pytest.raises(MissingRequiredArgument) as missing:
        command.convert_arguments(())
    assert missing.value.parameter == "width"

    with pytest.raises(BadArgument) as invalid:
        command.convert_arguments(("wide",))
    assert invalid.value.parameter == "width"

    with pytest.raises(TooManyArguments):
        command.convert_arguments(("1", "2", "3"))


async def test_prefix_adapter_preserves_quoted_arguments() -> None:
    async def echo(context: Context, value: str) -> None:
        pass

    registry = CommandRegistry()
    registry.add(Command.from_callback(echo))
    parsed = PrefixCommandAdapter(("/", "!")).parse('!echo "hello world"', registry)

    assert parsed is not None
    _, invocation = parsed
    assert invocation.arguments == ("hello world",)
    assert invocation.prefix == "!"


async def test_prefix_adapter_reports_parsing_and_unknown_commands() -> None:
    registry = CommandRegistry()
    adapter = PrefixCommandAdapter("!")

    with pytest.raises(CommandParsingError):
        adapter.parse('!echo "unfinished', registry)
    with pytest.raises(CommandNotFound):
        adapter.parse("!unknown", registry)


async def test_bot_invokes_typed_alias_and_lifecycle_events() -> None:
    runtime = Bot(token="vrb_secret")
    lifecycle: list[str] = []
    received: list[int] = []

    @runtime.event
    async def on_command(context: Context) -> None:
        lifecycle.append(f"start:{context.invoked_with}")

    @runtime.event
    async def on_command_complete(context: Context) -> None:
        lifecycle.append(f"complete:{context.command}")

    @runtime.command(aliases=("double",), description="Double a number")
    async def multiply(context: Context, value: int) -> None:
        received.append(value * 2)

    await runtime._handle_message(MessageUpserted(incoming_message("!double 21"), "1"))
    await runtime.close()

    assert received == [42]
    assert lifecycle == ["start:double", "complete:multiply"]
    assert runtime.get_command("double") is runtime.get_command("multiply")


async def test_bot_dispatches_conversion_error_with_context() -> None:
    runtime = Bot(token="vrb_secret")
    captured: list[tuple[Exception, Context | None]] = []

    @runtime.event
    async def on_command_error(error: Exception, context: Context | None) -> None:
        captured.append((error, context))

    @runtime.command()
    async def count(context: Context, value: int) -> None:
        pass

    await runtime._handle_message(MessageUpserted(incoming_message("!count nope"), "1"))
    await runtime.close()

    assert isinstance(captured[0][0], BadArgument)
    assert captured[0][1] is not None
    assert captured[0][1].args == ("nope",)
