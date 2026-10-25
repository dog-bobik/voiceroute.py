# Команды

Командный движок не зависит от способа доставки. Сейчас `PrefixCommandAdapter` создаёт
вызовы из обычных сообщений; будущий interaction adapter сможет создавать те же вызовы
без изменения пользовательских обработчиков.

## Регистрация

```python
from voiceroute import Bot, Context

bot = Bot(token="...")


@bot.command(
    aliases=("p", "latency"),
    description="Проверить доступность бота",
    usage="ping",
)
async def ping(ctx: Context) -> None:
    await ctx.reply("Pong!")
```

`bot.commands` возвращает зарегистрированные команды без дубликатов aliases,
`bot.get_command("p")` ищет команду по основному имени или alias.

## Типизированные аргументы

Поддерживаются позиционные `str`, `int`, `float`, `bool`, их optional-варианты,
значения по умолчанию и вариативные аргументы.

```python
@bot.command(description="Повторить сообщение")
async def repeat(ctx: Context, count: int, text: str, loud: bool = False) -> None:
    value = text.upper() if loud else text
    await ctx.reply(" ".join(value for _ in range(count)))
```

```text
!repeat 3 "привет мир" yes
```

Текст разбирается по правилам `shlex`, поэтому кавычки сохраняют пробелы внутри одного
аргумента. Для `bool` принимаются `true/false`, `yes/no`, `on/off` и `1/0` без учёта
регистра. Контекст-обработчик без дополнительных параметров сохраняет исходные аргументы
в `ctx.args` для обратной совместимости.

## Группы

Путь команды задаётся пробелами. Короткий alias многоуровневой команды заменяет последний
сегмент пути.

```python
@bot.command(name="admin ban", aliases=("block",))
async def ban(ctx: Context, user_id: int, reason: str | None = None) -> None: ...
```

Оба вызова ведут к одной команде:

```text
!admin ban 42 spam
!admin block 42 spam
```

Alias с несколькими словами считается полным альтернативным путём.

## Lifecycle и ошибки

```python
@bot.event
async def on_command(ctx: Context) -> None: ...


@bot.event
async def on_command_complete(ctx: Context) -> None: ...


@bot.event
async def on_command_error(error: Exception, ctx: Context | None) -> None: ...
```

Основные ошибки:

- `CommandParsingError` — незакрытые кавычки или другое нарушение синтаксиса;
- `CommandNotFound` — путь не зарегистрирован;
- `MissingRequiredArgument` — отсутствует обязательный аргумент;
- `BadArgument` — значение нельзя преобразовать в объявленный тип;
- `TooManyArguments` — обработчик не принимает оставшиеся аргументы;
- `UnsupportedCommandParameter` — callback использует неподдерживаемую сигнатуру.

Неизвестные команды по умолчанию игнорируются. Ошибки разбора, конвертации и выполнения
передаются в `on_command_error`; без такого обработчика применяется существующий
`on_error`.

## Граница будущего API

Эти команды являются prefix-командами поверх сообщений и не регистрируются в интерфейсе
[VoiceRoute](https://voiceroute.cc). Они не выдают себя за server-native slash commands.
После появления interactions будет добавлен отдельный adapter к тому же command engine.
