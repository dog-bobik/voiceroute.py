from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from examples.community_assistant.config import CommunityAssistantConfig
from examples.community_assistant.extensions.diagnostics import Diagnostics
from examples.community_assistant.extensions.general import General
from examples.community_assistant.extensions.knowledge import FAQRepository, Knowledge
from examples.community_assistant.extensions.messages import (
    Messages,
    bot_owned_target,
    format_messages,
    has_message_target,
    target_sequence,
)
from examples.community_assistant.extensions.native import register_native_commands

from voiceroute import (
    Bot,
    Context,
    Forbidden,
    Message,
    NotFound,
    Permission,
    RateLimited,
    User,
)


class FakeMessages:
    def __init__(self, history: tuple[Message, ...] = ()) -> None:
        self.sent: list[tuple[str, UUID]] = []
        self.history_items = history
        self.actions: list[tuple[str, str, object]] = []

    async def send(
        self,
        *_args: Any,
        body: str = "",
        client_message_id: UUID,
        **_kwargs: Any,
    ) -> Message:
        if len(_args) >= 3:
            body = str(_args[2])
        self.sent.append((body, client_message_id))
        return make_message(body=body, author=User(2, "bot", "Bot", bot=True))

    async def history(self, *_args: Any, **_kwargs: Any) -> Any:
        return type("Page", (), {"items": self.history_items})()

    async def set_pin(self, _community: str, _channel: str, seq: str, *, pinned=True) -> None:
        self.actions.append(("pin", seq, pinned))

    async def set_reaction(
        self,
        _community: str,
        _channel: str,
        seq: str,
        emoji: str,
        *,
        active: bool,
    ) -> None:
        self.actions.append(("reaction", seq, (emoji, active)))


def make_message(
    *,
    body: str = "/ping",
    seq: str = "10",
    author: User | None = None,
    reply_to_seq: str | None = None,
) -> Message:
    return Message(
        seq=seq,
        community_id="community",
        channel_id="channel",
        body=body,
        author=author or User(1, "member", "Member"),
        reply_to_seq=reply_to_seq,
    )


def make_context(
    messages: FakeMessages,
    *args: str,
    command: str = "test",
    reply_to_seq: str | None = None,
) -> Context:
    return Context(
        message=make_message(reply_to_seq=reply_to_seq),
        command=command,
        args=args,
        _messages=messages,  # type: ignore[arg-type]
        prefix="/",
    )


def test_config_reads_optional_values_and_requires_token() -> None:
    config = CommunityAssistantConfig.from_env({"VOICEROUTE_BOT_TOKEN": " secret "})
    assert config.token == "secret"
    assert config.community_id is None
    assert config.channel_id is None
    assert config.command_prefix == "/"
    assert config.sync_application_commands is True
    assert config.gateway_intents == ()

    configured = CommunityAssistantConfig.from_env(
        {
            "VOICEROUTE_BOT_TOKEN": "token",
            "VOICEROUTE_GATEWAY_INTENTS": "communities, messages",
        }
    )
    assert configured.gateway_intents == ("communities", "messages")

    with pytest.raises(ValueError, match="VOICEROUTE_BOT_TOKEN"):
        CommunityAssistantConfig.from_env({})
    with pytest.raises(ValueError, match="COMMUNITY_ID"):
        CommunityAssistantConfig.from_env(
            {"VOICEROUTE_BOT_TOKEN": "token", "VOICEROUTE_CHANNEL_ID": "channel"}
        )
    with pytest.raises(ValueError, match="must be true or false"):
        CommunityAssistantConfig.from_env(
            {
                "VOICEROUTE_BOT_TOKEN": "token",
                "VOICEROUTE_SYNC_APPLICATION_COMMANDS": "sometimes",
            }
        )


def test_native_commands_cover_interactions_members_and_permissions() -> None:
    bot = Bot(token="vrb_test")
    register_native_commands(bot)

    commands = {
        item.definition.name: item.definition for item in bot.application_command_registry.commands
    }
    assert set(commands) == {"ping", "search", "whoami", "capabilities"}
    assert commands["search"].options[0].type.value == "STRING"
    assert commands["capabilities"].default_member_permissions == (Permission.MANAGE_MESSAGES,)


def test_native_panel_registers_with_signed_persistent_component() -> None:
    bot = Bot(token="vrb_test", component_secret="0123456789abcdef")
    register_native_commands(bot)

    assert bot.application_command_registry.get("panel") is not None
    assert bot.components is not None
    custom_id = bot.components.custom_id("assistant-refresh", "ready")
    assert len(custom_id) <= 100


def test_faq_repository_loads_json_and_rejects_duplicate_slugs(tmp_path: Path) -> None:
    faq_path = tmp_path / "faq.json"
    faq_path.write_text(
        json.dumps([{"slug": "start", "title": "Start", "content": "Answer"}]),
        encoding="utf-8",
    )
    assert FAQRepository(faq_path).load()[0].title == "Start"

    faq_path.write_text(
        json.dumps(
            [
                {"slug": "same", "title": "One", "content": "A"},
                {"slug": "SAME", "title": "Two", "content": "B"},
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unique"):
        FAQRepository(faq_path).load()


@pytest.mark.asyncio
async def test_help_ping_and_faq_commands(tmp_path: Path) -> None:
    bot = Bot(token="vrb_test")
    general = General(bot)
    messages = FakeMessages()
    await bot.add_extension(general)

    await general.help_command(make_context(messages, command="help"))
    await general.ping(make_context(messages, command="ping"))
    assert "Команды Community Assistant" in messages.sent[0][0]
    assert messages.sent[1][0].startswith("Pong! Обработка:")

    faq_path = tmp_path / "faq.json"
    faq_path.write_text(
        json.dumps([{"slug": "start", "title": "Начало", "content": "Ответ"}]),
        encoding="utf-8",
    )
    knowledge = Knowledge(FAQRepository(faq_path))
    await knowledge.faq(make_context(messages, command="faq"))
    await knowledge.faq(make_context(messages, "missing", command="faq"))
    await knowledge.faq(make_context(messages, "search", command="faq"))
    assert "start" in messages.sent[2][0]
    assert "Неизвестная тема" in messages.sent[3][0]
    assert "Укажите запрос" in messages.sent[4][0]
    await bot.close()


def test_search_formatting_is_bounded_and_readable() -> None:
    items = tuple(
        make_message(body="x" * 500, seq=str(index), author=User(index, "u", "User"))
        for index in range(12)
    )
    result = format_messages("Результаты:", items)
    assert len(result) <= 4000
    assert "#0 · User:" in result
    assert "…и ещё 2" in result or "…результат обрезан" in result


@pytest.mark.asyncio
async def test_management_checks_accept_explicit_sequence_or_reply() -> None:
    bot_message = make_message(seq="42", author=User(2, "bot", "Bot", bot=True))
    messages = FakeMessages((bot_message,))
    valid = make_context(messages, "42")
    invalid = make_context(messages, "abc")
    replied = make_context(messages, reply_to_seq="42")
    assert has_message_target(valid)
    assert not has_message_target(invalid)
    assert has_message_target(replied)
    assert target_sequence(replied) == "42"
    assert await bot_owned_target(valid)
    assert await bot_owned_target(replied)
    assert not await bot_owned_target(invalid)


@pytest.mark.asyncio
async def test_message_actions_target_replied_message_without_manual_sequence() -> None:
    bot = Bot(token="vrb_test")
    messages = FakeMessages((make_message(seq="42"),))
    bot.client.messages = messages  # type: ignore[assignment]
    extension = Messages(bot)

    await extension.pin(make_context(messages, command="pin", reply_to_seq="42"))
    await extension.react(make_context(messages, "👍", command="react", reply_to_seq="42"))

    assert messages.actions == [("pin", "42", True), ("reaction", "42", ("👍", True))]
    await bot.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (Forbidden(403, "no"), "Недостаточно прав"),
        (NotFound(404, "gone"), "не найден"),
        (RateLimited(429, "slow", retry_after=2.5), "2.5 с"),
    ],
)
async def test_api_errors_become_friendly_messages(error: Exception, expected: str) -> None:
    bot = Bot(token="vrb_test")
    diagnostics = Diagnostics(bot)
    messages = FakeMessages()
    await diagnostics.command_error(error, make_context(messages))
    assert expected in messages.sent[0][0]
    await bot.close()


@pytest.mark.asyncio
async def test_repeated_delivery_reuses_idempotency_key() -> None:
    messages = FakeMessages()
    first = make_context(messages, command="ping")
    repeated = make_context(messages, command="ping")
    await first.reply("Pong!")
    await repeated.reply("Pong!")
    assert messages.sent[0][1] == messages.sent[1][1]
