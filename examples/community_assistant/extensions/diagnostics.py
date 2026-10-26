"""Health reporting and friendly runtime errors."""

from __future__ import annotations

from voiceroute import (
    BadArgument,
    Bot,
    CheckFailure,
    CommandOnCooldown,
    Context,
    Extension,
    Forbidden,
    MaxConcurrencyReached,
    MissingRequiredArgument,
    NotFound,
    RateLimited,
    TooManyArguments,
    command,
    cooldown,
    listener,
)


class Diagnostics(Extension):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @command(name="health", description="Показать состояние runtime и checkpoints.")
    @cooldown(2, 10.0)
    async def health(self, context: Context) -> None:
        connected = self.bot.is_ready()
        store = self.bot.cursor_store
        store_name = store.__class__.__name__
        store_status = "доступно"
        path = getattr(store, "path", None)
        if path is not None:
            store_status = f"{path}"
        await context.reply(
            "Состояние Community Assistant:\n"
            f"• runtime: {self.bot.state.value}\n"
            f"• подключение: {'активно' if connected else 'не готово'}\n"
            f"• transport: {'Gateway' if self.bot.gateway is not None else 'legacy SSE'}\n"
            f"• каналов: {len(self.bot.listening_channels)}\n"
            f"• checkpoints: {store_name} ({store_status})"
        )

    @listener("on_message")
    async def unknown_command_hint(self, message: object) -> None:
        from voiceroute import Message

        if not isinstance(message, Message) or not self.bot._can_invoke_command(message):
            return
        try:
            parsed = self.bot.command_adapter.parse(message.body, self.bot.command_registry)
        except Exception as error:
            from voiceroute import CommandNotFound

            if not isinstance(error, CommandNotFound):
                return
            context = Context(
                message=message,
                command="unknown",
                args=(),
                _messages=self.bot.client.messages,
                prefix=self.bot._matching_prefix(message.body),
            )
            await context.reply("Неизвестная команда. Используйте /help.")
            return
        if parsed is None:
            return

    @listener("on_command_error")
    async def command_error(self, error: Exception, context: Context | None) -> None:
        if context is None:
            return
        if isinstance(error, Forbidden):
            text = "Недостаточно прав для этой операции."
        elif isinstance(error, NotFound):
            text = "Сообщение или канал не найден."
        elif isinstance(error, RateLimited):
            wait = f" Повторите через {error.retry_after:.1f} с." if error.retry_after else ""
            text = "VoiceRoute временно ограничил частоту запросов." + wait
        elif isinstance(error, CheckFailure):
            text = (
                "Команда отклонена проверкой: укажите числовой seq; удалять можно "
                "только сообщения бота."
            )
        elif isinstance(error, CommandOnCooldown):
            text = f"Слишком часто. Повторите через {error.retry_after:.1f} с."
        elif isinstance(error, MissingRequiredArgument):
            text = f"Не хватает аргумента: {error.parameter}. Используйте /help {error.command}."
        elif isinstance(error, TooManyArguments):
            text = f"Слишком много аргументов. Используйте /help {error.command}."
        elif isinstance(error, BadArgument):
            text = f"Некорректный аргумент {error.parameter}."
        elif isinstance(error, MaxConcurrencyReached):
            text = "Эта команда уже выполняется. Попробуйте ещё раз чуть позже."
        else:
            text = "Не удалось выполнить команду из-за внутренней ошибки."
        await context.reply(text)


async def setup(bot: Bot) -> Extension:
    return Diagnostics(bot)
