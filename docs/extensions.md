# Расширения

Расширение объединяет связанные команды, listeners и собственные ресурсы. Оно может быть
подключено как готовый экземпляр или загружено из Python-модуля.

## Класс расширения

```python
from voiceroute import Bot, Context, Extension, Message, command, listener


class Utility(Extension):
    async def setup(self, bot: Bot) -> None:
        self.cache = {}

    async def teardown(self, bot: Bot) -> None:
        self.cache.clear()

    @command(aliases=("p",), description="Проверить доступность")
    async def ping(self, ctx: Context) -> None:
        await ctx.reply("Pong!")

    @listener()
    async def on_message(self, message: Message) -> None: ...
```

Pipeline-декораторы сохраняются:

```python
@command()
@cooldown(2, 10)
@check(is_owner)
async def reload(self, ctx: Context) -> None: ...
```

`@command()` должен оставаться внешним декоратором декларации метода, а checks/cooldown
применяются к callback до создания `Command`.

## Подключение экземпляра

```python
extension = Utility()
await bot.add_extension(extension)

await bot.remove_extension(extension.qualified_name)
```

Регистрация атомарна: если одна из команд конфликтует или listener некорректен, уже
добавленные обработчики удаляются, вызывается `teardown`, а расширение не появляется в
`bot.extensions`.

При удалении снимаются только exact handlers данного экземпляра. Команды и listeners
других расширений продолжают работать.

## Загрузка модуля

Модуль предоставляет асинхронную factory-функцию:

```python
async def setup(bot: Bot) -> Extension:
    return Utility()
```

Управление:

```python
await bot.load_extension("my_bot.extensions.utility")
await bot.reload_extension("my_bot.extensions.utility")
await bot.unload_extension("my_bot.extensions.utility")
```

`reload_extension` сначала корректно выгружает старый экземпляр. Если импорт, factory или
регистрация новой версии завершается ошибкой, runtime повторно подключает предыдущий
экземпляр, чтобы бот не остался без рабочего расширения.

## Несколько listeners

Обычный `@bot.event` и extension listeners могут одновременно слушать одно событие.
Runtime вызывает их в порядке регистрации по snapshot списка, поэтому удаление listener во
время dispatch не ломает текущий проход.

Ошибки управления представлены `ExtensionError` и производными:

- `ExtensionAlreadyLoaded`;
- `ExtensionNotLoaded`;
- `ExtensionSetupError`.
