"""Persistent signed component routing independent of process memory."""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Awaitable, Callable

from voiceroute.commands.interactions import InteractionContext

ComponentCallback = Callable[[InteractionContext, str], Awaitable[None]]


class ComponentRouter:
    def __init__(
        self,
        secret: str | bytes,
        *,
        previous_secrets: tuple[str | bytes, ...] = (),
    ) -> None:
        values = tuple(
            item.encode() if isinstance(item, str) else item
            for item in (secret, *previous_secrets)
        )
        if any(len(value) < 16 for value in values):
            raise ValueError("component signing secret must contain at least 16 bytes")
        self._secrets = values
        self._routes: dict[str, ComponentCallback] = {}

    def register(self, route: str, callback: ComponentCallback) -> None:
        if not route or "." in route or len(route) > 24:
            raise ValueError("component route must be 1-24 characters without dots")
        if route in self._routes:
            raise ValueError(f"component route is already registered: {route}")
        self._routes[route] = callback

    def custom_id(self, route: str, payload: str = "") -> str:
        encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
        body = f"{route}.{encoded}"
        signature = hmac.new(self._secrets[0], body.encode(), hashlib.sha256).hexdigest()[:16]
        custom_id = f"{body}.{signature}"
        if len(custom_id) > 100:
            raise ValueError("signed component custom_id exceeds 100 characters")
        return custom_id

    async def dispatch(self, context: InteractionContext, custom_id: str) -> bool:
        try:
            route, encoded, signature = custom_id.split(".", 2)
        except ValueError:
            return False
        body = f"{route}.{encoded}"
        if not any(
            hmac.compare_digest(
                signature,
                hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()[:16],
            )
            for secret in self._secrets
        ):
            return False
        callback = self._routes.get(route)
        if callback is None:
            return False
        padding = "=" * (-len(encoded) % 4)
        try:
            payload = base64.urlsafe_b64decode(encoded + padding).decode()
        except (ValueError, UnicodeDecodeError):
            return False
        await callback(context, payload)
        return True
