"""Native slash commands used by the Community Assistant example."""

from __future__ import annotations

import time

from examples.community_assistant.extensions.messages import format_messages
from voiceroute import (
    Bot,
    CommandOption,
    CommandOptionType,
    InteractionContext,
    Permission,
)


def register_native_commands(bot: Bot) -> None:
    """Declare the complete native command registry synchronized by this example."""

    @bot.slash_command("ping", description="Проверить отклик бота")
    async def ping(context: InteractionContext) -> None:
        started = time.perf_counter()
        elapsed_ms = (time.perf_counter() - started) * 1000
        await context.respond(f"Pong! Обработка: {elapsed_ms:.2f} мс", ephemeral=True)

    @bot.slash_command(
        "search",
        description="Искать сообщения в текущем канале",
        options=(
            CommandOption(
                name="query",
                description="Текст для поиска",
                type=CommandOptionType.STRING,
                required=True,
                min_length=1,
                max_length=200,
            ),
            CommandOption(
                name="private",
                description="Показать результат только вам",
                type=CommandOptionType.BOOLEAN,
            ),
        ),
    )
    async def search(context: InteractionContext) -> None:
        query = str(context.options["query"])
        page = await bot.client.messages.search(
            context.community_id,
            context.channel_id,
            query,
        )
        await context.respond(
            format_messages(f"Результаты поиска «{query}»:", page.items),
            ephemeral=context.options.get("private") is True,
        )

    @bot.slash_command("whoami", description="Показать мои данные на сервере")
    async def whoami(context: InteractionContext) -> None:
        member = await context.fetch_member()
        roles = ", ".join(role.name for role in member.roles) or "без дополнительных ролей"
        presence = member.presence.status.value if member.presence is not None else "неизвестен"
        await context.respond(
            f"{member.display_name}\n"
            f"• ID: {member.id}\n"
            f"• роль: {member.role}\n"
            f"• роли: {roles}\n"
            f"• presence: {presence}",
            ephemeral=True,
        )

    @bot.slash_command(
        "capabilities",
        description="Показать права бота в этом канале",
        default_member_permissions=(Permission.MANAGE_MESSAGES,),
    )
    async def capabilities(context: InteractionContext) -> None:
        channels = await bot.client.communities.list_channels(context.community_id)
        channel = next((item for item in channels if item.id == context.channel_id), None)
        if channel is None:
            await context.respond("Канал больше недоступен боту.", ephemeral=True)
            return
        values = channel.permissions.to_values()
        await context.respond(
            "Права бота в этом канале:\n" + (", ".join(values) if values else "нет прав"),
            ephemeral=True,
        )
