"""General-purpose commands."""

from __future__ import annotations

import time

from voiceroute import (
    Bot,
    Context,
    Extension,
    Permission,
    bot_has_permissions,
    command,
    cooldown,
)


class General(Extension):
    """Help, latency, and project information."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @command(name="help", description="Показать команды или справку.", usage="[команда]")
    @cooldown(4, 10.0)
    async def help_command(self, context: Context) -> None:
        requested = " ".join(context.args).casefold()
        if requested:
            selected = self.bot.get_command(requested)
            if selected is None:
                await context.reply("Неизвестная команда. Используйте /help для списка.")
                return
            usage = f" {selected.usage}" if selected.usage else ""
            await context.reply(
                f"{context.prefix or '/'}{selected.name}{usage}\n"
                f"{selected.description or 'Описание не указано.'}"
            )
            return

        lines = ["Команды Community Assistant:"]
        for item in sorted(self.bot.commands, key=lambda value: value.name):
            usage = f" {item.usage}" if item.usage else ""
            lines.append(f"{context.prefix or '/'}{item.name}{usage} — {item.description}")
        await context.reply("\n".join(lines))

    @command(name="ping", description="Проверить отклик бота.")
    @cooldown(3, 5.0)
    async def ping(self, context: Context) -> None:
        started = time.perf_counter()
        elapsed_ms = (time.perf_counter() - started) * 1000
        await context.reply(f"Pong! Обработка: {elapsed_ms:.2f} мс")

    @command(name="about", description="Информация о боте и библиотеке.")
    @cooldown(2, 10.0)
    async def about(self, context: Context) -> None:
        await context.reply(
            "Community Assistant — демонстрационный бот для voiceroute.py. "
            "Он показывает prefix- и slash-команды, interactions, members, permissions, "
            "extensions, SSE, SQLite checkpoints и content API."
        )

    @command(name="permissions", description="Показать права бота в текущем канале.")
    @bot_has_permissions(Permission.VIEW_CHANNEL)
    @cooldown(2, 10.0)
    async def permissions(self, context: Context) -> None:
        effective = await context.fetch_bot_permissions()
        values = effective.to_values() if effective is not None else ()
        await context.reply(
            "Права бота в текущем канале:\n" + (", ".join(values) if values else "нет прав")
        )


async def setup(bot: Bot) -> Extension:
    return General(bot)
