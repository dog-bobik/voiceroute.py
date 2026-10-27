"""Persistent signed component routing independent of process memory."""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Awaitable, Callable

from voiceroute.commands.interactions import InteractionContext

ComponentCallback = Callable[[InteractionContext, str], Awaitable[None]]


class ComponentRouter:
    def __init__(self, secret: str | bytes) -> None:
        value = secret.encode() if isinstance(secret, str) else secret
        if len(value) < 16:
            raise ValueError("component signing secret must contain at least 16 bytes")
        self._secret = value
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
        signature = hmac.new(self._secret, body.encode(), hashlib.sha256).hexdigest()[:16]
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
        expected = hmac.new(self._secret, body.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(signature, expected):
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
