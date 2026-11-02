"""Community roles and channel permission overrides."""

import builtins
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import cast

from voiceroute.models import (
    ChannelPermissionSnapshot,
    EffectivePermissions,
    Permission,
    PermissionOverride,
    PermissionRegistry,
    PermissionSimulation,
    PermissionTargetType,
    Role,
    RolePage,
)
from voiceroute.transport import HTTPResult, Transport


class RolesAPI:
    """Manage roles, assignments, and channel permission overrides."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
        self._role_collection_etags: dict[str, str] = {}

    async def list_v1(
        self, community_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> tuple[Role, ...]:
        return (await self.list_page_v1(community_id, cursor=cursor, limit=limit)).items

    async def list_page_v1(
        self, community_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> RolePage:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        path = f"/api/v1/communities/{community_id}/roles"
        metadata_request = cast(
            Callable[..., Awaitable[HTTPResult]] | None,
            getattr(self._transport, "request_with_response", None),
        )
        if metadata_request is None:
            payload = (
                await self._transport.request(
                    "GET", path, params={"cursor": cursor, "limit": limit}
                )
                or {}
            )
            etag = None
        else:
            response = await metadata_request(
                "GET", path, params={"cursor": cursor, "limit": limit}
            )
            payload = response.payload or {}
            etag = response.etag
        if etag is not None:
            self._role_collection_etags[community_id] = etag
        values = payload.get("items", ())
        return RolePage(
            tuple(Role.from_dict(item) for item in values if isinstance(item, dict)),
            str(payload["nextCursor"]) if payload.get("nextCursor") is not None else None,
            etag,
        )

    async def get_v1(self, community_id: str, role_id: str) -> Role:
        payload = await self._transport.request(
            "GET", f"/api/v1/communities/{community_id}/roles/{role_id}"
        )
        return _required_role(payload, "looked up")

    async def create_v1(
        self,
        community_id: str,
        name: str,
        *,
        color: str | None = None,
        permissions: Sequence[Permission | str] = (),
        unicode_emoji: str | None = None,
        icon_expression_id: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Role:
        if not name or len(name) > 100:
            raise ValueError("role name must contain between 1 and 100 characters")
        payload = await self._transport.request(
            "POST",
            f"/api/v1/communities/{community_id}/roles",
            json={
                "name": name,
                "color": color,
                "permissions": [str(item) for item in permissions],
                "unicodeEmoji": unicode_emoji,
                "iconExpressionId": icon_expression_id,
            },
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return _required_role(payload, "created")

    async def update_v1(
        self,
        community_id: str,
        role_id: str,
        *,
        if_match: str,
        name: str | None = None,
        color: str | None = None,
        permissions: Sequence[Permission | str] | None = None,
        unicode_emoji: str | None = None,
        icon_expression_id: str | None = None,
        clear_icon: bool = False,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Role:
        body: dict[str, object] = {}
        if name is not None:
            if not name or len(name) > 100:
                raise ValueError("role name must contain between 1 and 100 characters")
            body["name"] = name
        if color is not None:
            body["color"] = color
        if permissions is not None:
            body["permissions"] = [str(item) for item in permissions]
        if unicode_emoji is not None:
            body["unicodeEmoji"] = unicode_emoji
        if icon_expression_id is not None:
            body["iconExpressionId"] = icon_expression_id
        if clear_icon:
            if icon_expression_id is not None:
                raise ValueError("clear_icon and icon_expression_id cannot be combined")
            body["iconExpressionId"] = None
            body["unicodeEmoji"] = None
        if not body:
            raise ValueError("at least one role field must be supplied")
        payload = await self._transport.request(
            "PATCH",
            f"/api/v1/communities/{community_id}/roles/{role_id}",
            json=body,
            if_match=if_match,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return _required_role(payload, "updated")

    async def delete_v1(
        self,
        community_id: str,
        role_id: str,
        *,
        if_match: str,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        await self._transport.request(
            "DELETE",
            f"/api/v1/communities/{community_id}/roles/{role_id}",
            if_match=if_match,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            retryable=True,
        )

    async def reorder_v1(
        self,
        community_id: str,
        role_ids: Sequence[str],
        *,
        if_match: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> tuple[Role, ...]:
        current_etag = if_match or self._role_collection_etags.get(community_id)
        if not current_etag:
            raise ValueError("if_match is required; fetch list_page_v1 first to capture the ETag")
        if len(set(role_ids)) != len(role_ids):
            raise ValueError("role_ids must be unique")
        payload = (
            await self._transport.request(
                "PUT",
                f"/api/v1/communities/{community_id}/roles/order",
                json={"roleIds": list(role_ids)},
                if_match=current_etag,
                idempotency_key=str(idempotency_key or uuid.uuid4()),
            )
            or {}
        )
        return tuple(
            Role.from_dict(item) for item in payload.get("items", ()) if isinstance(item, dict)
        )

    async def permission_registry(self) -> PermissionRegistry:
        payload = await self._transport.request("GET", "/api/v1/permissions")
        if payload is None:
            raise RuntimeError("VoiceRoute returned no permission registry")
        return PermissionRegistry.from_dict(payload)

    async def effective_permissions(
        self, community_id: str, user_id: int, *, channel_id: str | None = None
    ) -> EffectivePermissions:
        if user_id <= 0:
            raise ValueError("user_id must be positive")
        payload = await self._transport.request(
            "GET",
            f"/api/v1/communities/{community_id}/members/{user_id}/permissions",
            params={"channelId": channel_id},
        )
        return EffectivePermissions.from_dict(_required_object(payload, "effective permissions"))

    async def simulate_permissions(
        self,
        community_id: str,
        user_id: int,
        *,
        channel_id: str | None = None,
        role_ids: Sequence[str] = (),
        overrides: Sequence[Mapping[str, object]] = (),
    ) -> PermissionSimulation:
        if user_id <= 0 or len(set(role_ids)) != len(role_ids):
            raise ValueError("user_id must be positive and role_ids must be unique")
        payload = await self._transport.request(
            "POST",
            f"/api/v1/communities/{community_id}/permissions/simulate",
            json={
                "userId": str(user_id),
                "channelId": channel_id,
                "roleIds": list(role_ids),
                "overrides": [dict(item) for item in overrides],
            },
            idempotency_key=str(uuid.uuid4()),
        )
        return PermissionSimulation.from_dict(_required_object(payload, "permission simulation"))

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

    async def channel_permissions_v1(
        self, community_id: str, channel_id: str
    ) -> ChannelPermissionSnapshot:
        payload = await self._transport.request(
            "GET", f"/api/v1/communities/{community_id}/channels/{channel_id}/permissions"
        )
        return ChannelPermissionSnapshot.from_dict(payload or {})

    async def category_permissions_v1(
        self, community_id: str, category_id: str
    ) -> tuple[PermissionOverride, ...]:
        payload = (
            await self._transport.request(
                "GET", f"/api/v1/communities/{community_id}/categories/{category_id}/permissions"
            )
            or {}
        )
        values = payload.get("items", ())
        return tuple(
            PermissionOverride.from_dict(item) for item in values if isinstance(item, dict)
        )

    async def replace_category_overrides_v1(
        self,
        community_id: str,
        category_id: str,
        overrides: Sequence[PermissionOverride],
        *,
        if_match: str,
        audit_reason: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> tuple[PermissionOverride, ...]:
        if len(overrides) > 100:
            raise ValueError("at most 100 permission overrides are supported")
        payload = (
            await self._transport.request(
                "PUT",
                f"/api/v1/communities/{community_id}/categories/{category_id}/permissions",
                json={"overrides": [_override_dict(item) for item in overrides]},
                headers=_audit_headers(audit_reason),
                if_match=if_match,
                idempotency_key=str(idempotency_key or uuid.uuid4()),
            )
            or {}
        )
        return tuple(
            PermissionOverride.from_dict(item)
            for item in payload.get("items", ())
            if isinstance(item, dict)
        )

    async def replace_channel_overrides_v1(
        self,
        community_id: str,
        channel_id: str,
        overrides: Sequence[PermissionOverride],
        *,
        if_match: str,
        audit_reason: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> ChannelPermissionSnapshot:
        if len(overrides) > 100:
            raise ValueError("at most 100 permission overrides are supported")
        payload = await self._transport.request(
            "PUT",
            f"/api/v1/communities/{community_id}/channels/{channel_id}/permissions",
            json={"overrides": [_override_dict(item) for item in overrides]},
            headers=_audit_headers(audit_reason),
            if_match=if_match,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return ChannelPermissionSnapshot.from_dict(payload or {})

    async def sync_channel_overrides_v1(
        self,
        community_id: str,
        channel_id: str,
        *,
        if_match: str,
        audit_reason: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> ChannelPermissionSnapshot:
        """Copy category overrides onto a channel with optimistic concurrency."""
        if not if_match:
            raise ValueError("if_match is required to sync channel overrides")
        payload = await self._transport.request(
            "PUT",
            f"/api/v1/communities/{community_id}/channels/{channel_id}/permissions/sync",
            headers=_audit_headers(audit_reason),
            if_match=if_match,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return ChannelPermissionSnapshot.from_dict(payload or {})

    async def add_member_role_v1(
        self,
        community_id: str,
        user_id: int,
        role_id: str,
        *,
        if_match: str,
        audit_reason: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        await self._member_role_request(
            "PUT",
            community_id,
            user_id,
            role_id,
            if_match=if_match,
            audit_reason=audit_reason,
            idempotency_key=idempotency_key,
        )

    async def remove_member_role_v1(
        self,
        community_id: str,
        user_id: int,
        role_id: str,
        *,
        if_match: str,
        audit_reason: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        await self._member_role_request(
            "DELETE",
            community_id,
            user_id,
            role_id,
            if_match=if_match,
            audit_reason=audit_reason,
            idempotency_key=idempotency_key,
        )

    async def _member_role_request(
        self,
        method: str,
        community_id: str,
        user_id: int,
        role_id: str,
        *,
        if_match: str,
        audit_reason: str | None,
        idempotency_key: str | uuid.UUID | None,
    ) -> None:
        if user_id <= 0:
            raise ValueError("user_id must be positive")
        await self._transport.request(
            method,
            f"/api/v1/communities/{community_id}/members/{user_id}/roles/{role_id}",
            headers=_audit_headers(audit_reason),
            if_match=if_match,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            retryable=True,
        )


def _permission_values(values: Sequence[Permission | str]) -> list[str]:
    return list(dict.fromkeys(Permission(value).value for value in values))


def _required_role(payload: dict[str, object] | None, operation: str) -> Role:
    raw_role = payload.get("role") if payload is not None else None
    if not isinstance(raw_role, dict):
        raise RuntimeError(f"VoiceRoute returned no {operation} role")
    return Role.from_dict(raw_role)


def _required_object(payload: dict[str, object] | None, operation: str) -> dict[str, object]:
    if payload is None:
        raise RuntimeError(f"VoiceRoute returned no response after {operation}")
    return payload


def _override_dict(item: PermissionOverride) -> dict[str, object]:
    return {
        "targetType": item.target_type.value,
        "targetId": item.target_id,
        "allow": item.allow.to_values(),
        "deny": item.deny.to_values(),
    }


def _audit_headers(reason: str | None) -> dict[str, str]:
    if reason is None:
        return {}
    if len(reason) > 512:
        raise ValueError("audit reason cannot exceed 512 characters")
    return {"X-Audit-Log-Reason": reason}
