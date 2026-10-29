"""Bot-side Mini App state and action lifecycle API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from voiceroute.transport import HTTPTransport


@dataclass(frozen=True, slots=True)
class MiniAppState:
    """Shared state snapshot for one opaque Mini App instance."""

    instance_id: str
    version: str
    state: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MiniAppState:
        raw_state = data.get("state")
        return cls(
            instance_id=str(data["instanceId"]),
            version=str(data["version"]),
            state=dict(raw_state) if isinstance(raw_state, dict) else {},
        )


class MiniAppsAPI:
    """Read shared state and resolve user-created Mini App actions."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    @staticmethod
    def _base(application_id: str) -> str:
        return f"/api/v1/applications/{application_id}/mini-app"

    async def get_state(self, application_id: str, instance_id: str) -> MiniAppState:
        payload = await self._transport.request(
            "GET", f"{self._base(application_id)}/instances/{instance_id}/state"
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no Mini App state")
        return MiniAppState.from_dict(payload)

    async def acknowledge_action(
        self,
        application_id: str,
        action_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return await self._action_request(
            application_id, action_id, "ack", {}, idempotency_key=idempotency_key
        )

    async def complete_action(
        self,
        application_id: str,
        action_id: str,
        *,
        result: Any = None,
        state: dict[str, Any] | None = None,
        version: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if (state is None) != (version is None):
            raise ValueError("state and version must be provided together")
        body: dict[str, Any] = {"result": result}
        if state is not None:
            body["state"] = state
        return await self._action_request(
            application_id,
            action_id,
            "complete",
            body,
            version=version,
            idempotency_key=idempotency_key,
        )

    async def reject_action(
        self,
        application_id: str,
        action_id: str,
        code: str = "ACTION_REJECTED",
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return await self._action_request(
            application_id,
            action_id,
            "reject",
            {"code": code},
            idempotency_key=idempotency_key,
        )

    async def _action_request(
        self,
        application_id: str,
        action_id: str,
        operation: str,
        body: dict[str, Any],
        *,
        version: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload = await self._transport.request(
            "POST",
            f"{self._base(application_id)}/actions/{action_id}/{operation}",
            json=body,
            if_match=f'"state-{version}"' if version is not None else None,
            idempotency_key=idempotency_key,
            generate_idempotency_key=idempotency_key is None,
        )
        return payload or {}
