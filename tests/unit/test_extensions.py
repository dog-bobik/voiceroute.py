from types import ModuleType
from unittest.mock import AsyncMock, patch

import pytest

from voiceroute import (
    Bot,
    Context,
    Extension,
    ExtensionAlreadyLoaded,
    ExtensionNotLoaded,
    ExtensionSetupError,
    check,
    command,
    listener,
)
from voiceroute.events import MessageUpserted
from voiceroute.models import Message, User


def incoming_message(body: str) -> Message:
    return Message(
        seq="17",
        community_id="community",
        channel_id="channel",
        body=body,
        author=User(7, "member", "Member"),
    )


class UtilityExtension(Extension):
    def __init__(self) -> None:
        self.lifecycle: list[str] = []
        self.messages: list[str] = []

    async def setup(self, bot: Bot) -> None:
        self.lifecycle.append("setup")

    async def teardown(self, bot: Bot) -> None:
        self.lifecycle.append("teardown")

    @command(aliases=("p",), description="Check availability")
    async def ping(self, ctx: Context) -> None:
        self.messages.append("command")

    @listener()
    async def on_message(self, message: Message) -> None:
        self.messages.append(message.body)


async def test_extension_registers_and_removes_commands_and_listeners() -> None:
    bot = Bot(token="vrb_secret")
    extension = UtilityExtension()

    await bot.add_extension(extension)
    await bot._handle_message(MessageUpserted(incoming_message("!p"), "1"))

    assert extension.lifecycle == ["setup"]
    assert extension.messages == ["!p", "command"]
    assert bot.get_command("ping") is not None
    assert bot.extensions == (extension,)

    await bot.remove_extension(extension.qualified_name)
    await bot._handle_message(MessageUpserted(incoming_message("!p"), "2"))
    await bot.close()

    assert extension.lifecycle == ["setup", "teardown"]
    assert extension.messages == ["!p", "command"]
    assert bot.get_command("ping") is None
    assert bot.extensions == ()


async def test_multiple_event_listeners_are_dispatched() -> None:
    bot = Bot(token="vrb_secret")
    received: list[str] = []

    @bot.event
    async def on_message(message: Message) -> None:
        received.append("first")

    async def second(message: Message) -> None:
        received.append("second")

    bot.add_listener(second, "on_message")
    await bot._dispatch("on_message", incoming_message("hello"))
    bot.remove_listener(second, "on_message")
    await bot._dispatch("on_message", incoming_message("again"))
    await bot.close()

    assert received == ["first", "second", "first"]


async def test_duplicate_extension_is_rejected() -> None:
    bot = Bot(token="vrb_secret")
    extension = UtilityExtension()
    await bot.add_extension(extension)

    with pytest.raises(ExtensionAlreadyLoaded):
        await bot.add_extension(UtilityExtension())

    await bot.close()


async def test_partial_registration_rolls_back() -> None:
    bot = Bot(token="vrb_secret")

    @bot.command("taken")
    async def taken(ctx: Context) -> None:
        pass

    class ConflictingExtension(Extension):
        def __init__(self) -> None:
            self.torn_down = False

        async def teardown(self, bot: Bot) -> None:
            self.torn_down = True

        @command("available")
        async def available(self, ctx: Context) -> None:
            pass

        @command("taken")
        async def conflict(self, ctx: Context) -> None:
            pass

    extension = ConflictingExtension()
    with pytest.raises(ValueError, match="already registered"):
        await bot.add_extension(extension)

    assert bot.get_command("available") is None
    assert bot.get_command("taken") is not None
    assert extension.torn_down is True
    await bot.close()


async def test_extension_command_preserves_pipeline_metadata() -> None:
    denied = AsyncMock(return_value=False)

    class ProtectedExtension(Extension):
        @command()
        @check(denied)
        async def protected(self, ctx: Context) -> None:
            pass

    bot = Bot(token="vrb_secret")
    await bot.add_extension(ProtectedExtension())
    errors: list[Exception] = []

    @bot.event
    async def on_command_error(error: Exception, ctx: Context | None) -> None:
        errors.append(error)

    await bot._handle_message(MessageUpserted(incoming_message("!protected"), "1"))
    await bot.close()

    denied.assert_awaited_once()
    assert errors


async def test_load_and_unload_extension_module() -> None:
    module = ModuleType("test_extension")

    async def setup(bot: Bot) -> Extension:
        return UtilityExtension()

    module.setup = setup  # type: ignore[attr-defined]
    bot = Bot(token="vrb_secret")
    with patch("voiceroute.bot.importlib.import_module", return_value=module):
        extension = await bot.load_extension("test_extension")
        assert bot.extensions == (extension,)
        removed = await bot.unload_extension("test_extension")

    assert removed is extension
    assert extension.lifecycle == ["setup", "teardown"]
    await bot.close()


async def test_invalid_or_missing_extension_module_contract() -> None:
    bot = Bot(token="vrb_secret")
    module = ModuleType("invalid_extension")

    with patch("voiceroute.bot.importlib.import_module", return_value=module):
        with pytest.raises(ExtensionSetupError, match="async setup"):
            await bot.load_extension("invalid_extension")

    with pytest.raises(ExtensionNotLoaded):
        await bot.unload_extension("missing")
    await bot.close()
