"""Commands backed by VoiceRoute's message content API."""

from __future__ import annotations

from collections.abc import Awaitable

from voiceroute import Bot, Context, Extension, Message, check, command, cooldown

MESSAGE_LIMIT = 4000
RESULT_LIMIT = 10


def target_sequence(context: Context) -> str | None:
    """Resolve an explicit sequence first, then fall back to the replied message."""
    if context.args:
        return context.args[0] if context.args[0].isdigit() else None
    return context.replied_message_seq


def has_message_target(context: Context) -> bool:
    return target_sequence(context) is not None


def has_reaction_target(context: Context) -> bool:
    return bool(
        context.args and (context.args[0].isdigit() or context.replied_message_seq is not None)
    )


async def bot_owned_target(context: Context) -> bool:
    sequence = target_sequence(context)
    if sequence is None:
        return False
    target = await context.fetch_message(sequence)
    return bool(target is not None and target.author is not None and target.author.bot)


def format_messages(title: str, messages: tuple[Message, ...]) -> str:
    lines = [title]
    for message in messages[:RESULT_LIMIT]:
        author = message.author.display_name if message.author is not None else "неизвестный автор"
        body = " ".join(message.body.split()) or "(без текста)"
        lines.append(f"#{message.seq} · {author}: {body}")
    if not messages:
        lines.append("Ничего не найдено.")
    elif len(messages) > RESULT_LIMIT:
        lines.append(f"…и ещё {len(messages) - RESULT_LIMIT}")
    return truncate_message("\n".join(lines))


def truncate_message(value: str, limit: int = MESSAGE_LIMIT) -> str:
    if len(value) <= limit:
        return value
    suffix = "\n…результат обрезан"
    return value[: limit - len(suffix)].rstrip() + suffix


class Messages(Extension):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def _run_action(
        self,
        context: Context,
        action: Awaitable[object],
        confirmation: str,
    ) -> None:
        await action
        await context.reply(confirmation)

    @command(name="search", description="Искать сообщения в текущем канале.", usage="<запрос>")
    @cooldown(3, 10.0)
    async def search(self, context: Context) -> None:
        query = " ".join(context.args).strip()
        if not query:
            await context.reply("Укажите запрос: /search <запрос>")
            return
        page = await self.bot.client.messages.search(
            context.message.community_id,
            context.message.channel_id,
            query,
        )
        await context.reply(format_messages(f"Результаты поиска «{query}»:", page.items))

    @command(name="pins", description="Показать закреплённые сообщения.")
    @cooldown(3, 10.0)
    async def pins(self, context: Context) -> None:
        page = await self.bot.client.messages.pins(
            context.message.community_id,
            context.message.channel_id,
        )
        await context.reply(format_messages("Закреплённые сообщения:", page.items))

    @command(name="pin", description="Закрепить сообщение.", usage="[seq] или reply")
    @check(has_message_target)
    @cooldown(2, 10.0)
    async def pin(self, context: Context, seq: str | None = None) -> None:
        target = target_sequence(context)
        if target is None:
            return
        await self._run_action(
            context,
            self.bot.client.messages.set_pin(
                context.message.community_id, context.message.channel_id, target
            ),
            f"Сообщение #{target} закреплено.",
        )

    @command(name="unpin", description="Снять закрепление.", usage="[seq] или reply")
    @check(has_message_target)
    @cooldown(2, 10.0)
    async def unpin(self, context: Context, seq: str | None = None) -> None:
        target = target_sequence(context)
        if target is None:
            return
        await self._run_action(
            context,
            self.bot.client.messages.set_pin(
                context.message.community_id,
                context.message.channel_id,
                target,
                pinned=False,
            ),
            f"Сообщение #{target} откреплено.",
        )

    @command(name="react", description="Добавить реакцию.", usage="[seq] <emoji> или reply")
    @check(has_reaction_target)
    @cooldown(4, 10.0)
    async def react(self, context: Context) -> None:
        await self._reaction_from_context(context, active=True)

    @command(name="unreact", description="Удалить реакцию.", usage="[seq] <emoji> или reply")
    @check(has_reaction_target)
    @cooldown(4, 10.0)
    async def unreact(self, context: Context) -> None:
        await self._reaction_from_context(context, active=False)

    async def _reaction_from_context(self, context: Context, *, active: bool) -> None:
        explicit_sequence = bool(context.args and context.args[0].isdigit())
        sequence = context.args[0] if explicit_sequence else context.replied_message_seq
        emoji_index = 1 if explicit_sequence else 0
        if sequence is None or len(context.args) != emoji_index + 1:
            await context.reply(
                "Ответьте командой на сообщение и укажите emoji либо используйте "
                f"/{context.command} <seq> <emoji>."
            )
            return
        await self._set_reaction(context, sequence, context.args[emoji_index], active=active)

    async def _set_reaction(self, context: Context, seq: str, emoji: str, *, active: bool) -> None:
        await self._run_action(
            context,
            self.bot.client.messages.set_reaction(
                context.message.community_id,
                context.message.channel_id,
                seq,
                emoji,
                active=active,
            ),
            f"Реакция {emoji} {'добавлена' if active else 'удалена'} для #{seq}.",
        )

    @command(name="delete", description="Удалить сообщение бота.", usage="[seq] или reply")
    @check(bot_owned_target)
    @cooldown(1, 10.0)
    async def delete(self, context: Context, seq: str | None = None) -> None:
        sequence = target_sequence(context)
        if sequence is None:
            return
        target = await context.fetch_message(sequence)
        own_user = self.bot.user.user if self.bot.user is not None else None
        if target is None or target.author is None or own_user is None:
            await context.reply("Нельзя подтвердить, что это сообщение принадлежит текущему боту.")
            return
        if target.author.id != own_user.id:
            await context.reply("Удалять можно только сообщения текущего бота.")
            return
        await self._run_action(
            context,
            self.bot.client.messages.delete(
                context.message.community_id, context.message.channel_id, sequence
            ),
            f"Сообщение бота #{sequence} удалено.",
        )


async def setup(bot: Bot) -> Extension:
    return Messages(bot)
