"""Community roles and channel permission overrides."""

import builtins
from collections.abc import Sequence

from voiceroute.models import (
    ChannelPermissionSnapshot,
    Permission,
    PermissionOverride,
    PermissionTargetType,
    Role,
)
from voiceroute.transport import HTTPTransport


class RolesAPI:
    """Manage roles, assignments, and channel permission overrides."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def list(self, community_id: str) -> builtins.list[Role]:
        payload = await self._transport.request("GET", f"/api/communities/{community_id}/roles")
        if payload is None:
            return []
        return [Role.from_dict(item) for item in payload.get("items", [])]

    async def create(
        self,
        community_id: str,
        name: str,
        *,
        color: str | None = None,
        permissions: Sequence[Permission | str] = (),
    ) -> Role:
        payload = await self._transport.request(
            "POST",
            f"/api/communities/{community_id}/roles",
            json={
                "name": name,
                "color": color,
                "permissions": _permission_values(permissions),
            },
        )
        return _required_role(payload, "created")

    async def edit(
        self,
        community_id: str,
        role_id: str,
        *,
        name: str | None = None,
        color: str | None = None,
        clear_color: bool = False,
        position: int | None = None,
        permissions: Sequence[Permission | str] | None = None,
    ) -> Role:
        if color is not None and clear_color:
            raise ValueError("color and clear_color cannot be used together")
        data: dict[str, object] = {}
        if name is not None:
            data["name"] = name
        if color is not None or clear_color:
            data["color"] = color
        if position is not None:
            data["position"] = position
        if permissions is not None:
            data["permissions"] = _permission_values(permissions)
        payload = await self._transport.request(
            "PATCH",
            f"/api/communities/{community_id}/roles/{role_id}",
            json=data,
        )
        return _required_role(payload, "updated")

    async def delete(self, community_id: str, role_id: str) -> None:
        await self._transport.request(
            "DELETE",
            f"/api/communities/{community_id}/roles/{role_id}",
        )

    async def set_member_roles(
        self,
        community_id: str,
        user_id: int,
        role_ids: Sequence[str],
    ) -> tuple[str, ...]:
        payload = await self._transport.request(
            "PUT",
            f"/api/communities/{community_id}/members/{user_id}/roles",
            json={"roleIds": list(dict.fromkeys(role_ids))},
        )
        if payload is None:
            return ()
        return tuple(str(value) for value in payload.get("roleIds", ()))

    async def channel_permissions(
        self,
        community_id: str,
        channel_id: str,
    ) -> ChannelPermissionSnapshot:
        payload = await self._transport.request(
            "GET",
            f"/api/communities/{community_id}/channels/{channel_id}/permissions",
        )
        return ChannelPermissionSnapshot.from_dict(payload or {})

    async def set_channel_override(
        self,
        community_id: str,
        channel_id: str,
        target_type: PermissionTargetType | str,
        target_id: str | int,
        *,
        allow: Sequence[Permission | str] = (),
        deny: Sequence[Permission | str] = (),
    ) -> PermissionOverride:
        allowed = _permission_values(allow)
        denied = _permission_values(deny)
        if set(allowed) & set(denied):
            raise ValueError("the same permission cannot be allowed and denied")
        payload = await self._transport.request(
            "PUT",
            f"/api/communities/{community_id}/channels/{channel_id}/permissions",
            json={
                "targetType": PermissionTargetType(target_type).value,
                "targetId": str(target_id),
                "allow": allowed,
                "deny": denied,
            },
        )
        if payload is None or not isinstance(payload.get("override"), dict):
            raise RuntimeError("VoiceRoute returned no permission override")
        return PermissionOverride.from_dict(payload["override"])


def _permission_values(values: Sequence[Permission | str]) -> list[str]:
    return list(dict.fromkeys(Permission(value).value for value in values))


def _required_role(payload: dict[str, object] | None, operation: str) -> Role:
    raw_role = payload.get("role") if payload is not None else None
    if not isinstance(raw_role, dict):
        raise RuntimeError(f"VoiceRoute returned no {operation} role")
    return Role.from_dict(raw_role)
