"""Optional command pipeline middleware for FSM context injection/isolation."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Protocol

from voiceroute.commands.context import Context
from voiceroute.fsm.core import FSMContext, FSMKey, FSMStorage


class Next(Protocol):
    async def __call__(self) -> None: ...


FSMKeyFactory = Callable[[Context], FSMKey | Awaitable[FSMKey]]


def fsm_middleware(
    storage: FSMStorage,
    key_factory: FSMKeyFactory,
    *,
    context_name: str = "fsm",
) -> Callable[[Context, Next], Awaitable[None]]:
    """Inject an FSM context and serialize a handler by its configured key.

    The key factory makes origin and application identity explicit instead of
    guessing them from partial message data.
    """
    if not context_name:
        raise ValueError("context_name cannot be empty")

    async def middleware(context: Context, call_next: Next) -> None:
        key = key_factory(context)
        if inspect.isawaitable(key):
            key = await key
        context.data[context_name] = FSMContext(storage, key)
        async with storage.isolate(key):
            await call_next()

    return middleware
