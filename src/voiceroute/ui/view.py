"""Lifecycle helpers for persistent, signed component views."""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable

from voiceroute.commands.components import ComponentRouter
from voiceroute.commands.interactions import InteractionContext
from voiceroute.models import ActionRow, Component

ViewCallback = Callable[[InteractionContext, str], Awaitable[None]]


class View:
    """Group supported components and bind their callbacks to a persistent route.

    Recreate and register the same route during application startup to restore a
    persistent view after a process restart. A finite timeout is process-local.
    """

    def __init__(
        self,
        router: ComponentRouter,
        route: str,
        *,
        timeout: float | None = 180.0,
        owner_id: int | None = None,
    ) -> None:
        if timeout is not None and timeout <= 0:
            raise ValueError("timeout must be positive or None")
        if owner_id is not None and owner_id <= 0:
            raise ValueError("owner_id must be positive")
        self.route = route
        self.owner_id = owner_id
        self._timeout = timeout
        self._expires_at = time.monotonic() + timeout if timeout is not None else None
        self._router = router
        self._items: dict[str, tuple[Component, ViewCallback]] = {}
        self._stopped = False
        router.register(route, self._dispatch)

    @property
    def is_finished(self) -> bool:
        return self._stopped or (
            self._expires_at is not None and time.monotonic() >= self._expires_at
        )

    @property
    def persistent(self) -> bool:
        return self._timeout is None

    @property
    def components(self) -> tuple[ActionRow, ...]:
        values = tuple(item[0] for item in self._items.values())
        return tuple(ActionRow(values[offset : offset + 5]) for offset in range(0, len(values), 5))

    def add_item(
        self,
        item_id: str,
        component: Component,
        callback: ViewCallback,
        *,
        payload: str = "",
    ) -> Component:
        if self.is_finished:
            raise RuntimeError("cannot add items to a finished view")
        if not item_id or len(item_id) > 24 or "." in item_id:
            raise ValueError("item_id must contain 1-24 characters without dots")
        if item_id in self._items:
            raise ValueError(f"view item is already registered: {item_id}")
        if len(self._items) >= 25:
            raise ValueError("a view cannot contain more than 25 components")
        if component.style is not None and component.style.value == "LINK":
            raise ValueError("link buttons do not dispatch component callbacks")
        encoded_data = json.dumps([item_id, payload], separators=(",", ":"))
        signed_id = self._router.custom_id(self.route, encoded_data)
        bound = Component(
            type=component.type,
            custom_id=signed_id,
            style=component.style,
            label=component.label,
            url=component.url,
            emoji=component.emoji,
            disabled=component.disabled,
            accessibility_label=component.accessibility_label,
            placeholder=component.placeholder,
            min_values=component.min_values,
            max_values=component.max_values,
            channel_types=component.channel_types,
            options=component.options,
        )
        self._items[item_id] = (bound, callback)
        return bound

    def stop(self) -> None:
        self._stopped = True

    def disable_all(self) -> tuple[ActionRow, ...]:
        return tuple(
            ActionRow(
                tuple(
                    Component(
                        type=item.type,
                        custom_id=item.custom_id,
                        style=item.style,
                        label=item.label,
                        url=item.url,
                        emoji=item.emoji,
                        disabled=True,
                        accessibility_label=item.accessibility_label,
                        placeholder=item.placeholder,
                        min_values=item.min_values,
                        max_values=item.max_values,
                        channel_types=item.channel_types,
                        options=item.options,
                    )
                    for item in row.components
                )
            )
            for row in self.components
        )

    async def _dispatch(self, context: InteractionContext, value: str) -> None:
        if self.is_finished:
            return
        if self.owner_id is not None and context.user_id != self.owner_id:
            await context.respond("This control belongs to another user.", ephemeral=True)
            return
        try:
            item_id, payload = json.loads(value)
        except (TypeError, ValueError):
            return
        item = self._items.get(item_id)
        if item is None:
            return
        await item[1](context, str(payload))
