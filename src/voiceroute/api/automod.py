"""Automatic moderation endpoints."""

import unicodedata
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from voiceroute.models import AutoModConfig, AutoModRule, AutoModRulePage
from voiceroute.transport import Transport


class AutoModAPI:
    """Read and replace a community's automatic moderation policy."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def list_rules(
        self, community_id: str, *, cursor: str | None = None, limit: int = 20
    ) -> AutoModRulePage:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        payload = (
            await self._transport.request(
                "GET",
                f"/api/v1/communities/{community_id}/automod/rules",
                params={"cursor": cursor, "limit": limit},
            )
            or {}
        )
        values = payload.get("items", ())
        return AutoModRulePage(
            tuple(AutoModRule.from_dict(item) for item in values if isinstance(item, dict)),
            str(payload["nextCursor"]) if payload.get("nextCursor") is not None else None,
        )

    async def get_rule(self, community_id: str, rule_id: str) -> AutoModRule:
        payload = await self._transport.request(
            "GET", f"/api/v1/communities/{community_id}/automod/rules/{rule_id}"
        )
        return AutoModRule.from_dict(_rule_object(payload))

    async def create_rule(
        self,
        community_id: str,
        *,
        name: str,
        trigger: str,
        metadata: Mapping[str, Any],
        actions: Sequence[Mapping[str, Any]],
        enabled: bool = True,
        exempt_role_ids: Sequence[str] = (),
        exempt_channel_ids: Sequence[str] = (),
        idempotency_key: str | uuid.UUID | None = None,
    ) -> AutoModRule:
        body = _rule_body(
            name, trigger, metadata, actions, enabled, exempt_role_ids, exempt_channel_ids
        )
        payload = await self._transport.request(
            "POST",
            f"/api/v1/communities/{community_id}/automod/rules",
            json=body,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return AutoModRule.from_dict(_rule_object(payload))

    async def update_rule(
        self,
        community_id: str,
        rule_id: str,
        *,
        if_match: str,
        name: str | None = None,
        enabled: bool | None = None,
        trigger: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        actions: Sequence[Mapping[str, Any]] | None = None,
        exempt_role_ids: Sequence[str] | None = None,
        exempt_channel_ids: Sequence[str] | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> AutoModRule:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if enabled is not None:
            body["enabled"] = enabled
        if trigger is not None:
            body["trigger"] = trigger
        if metadata is not None:
            body["metadata"] = dict(metadata)
        if actions is not None:
            body["actions"] = [dict(action) for action in actions]
        if exempt_role_ids is not None:
            body["exemptRoleIds"] = list(exempt_role_ids)
        if exempt_channel_ids is not None:
            body["exemptChannelIds"] = list(exempt_channel_ids)
        if not body:
            raise ValueError("at least one automatic moderation rule field is required")
        if name is not None:
            _validate_rule_name(name)
        payload = await self._transport.request(
            "PATCH",
            f"/api/v1/communities/{community_id}/automod/rules/{rule_id}",
            json=body,
            if_match=if_match,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return AutoModRule.from_dict(_rule_object(payload))

    async def delete_rule(
        self,
        community_id: str,
        rule_id: str,
        *,
        if_match: str,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        await self._transport.request(
            "DELETE",
            f"/api/v1/communities/{community_id}/automod/rules/{rule_id}",
            if_match=if_match,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            retryable=True,
        )

    async def actions(
        self, community_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> tuple[dict[str, Any], ...]:
        return await self._list_v1_metadata(
            f"/api/v1/communities/{community_id}/automod/actions", cursor, limit
        )

    async def alerts(
        self, community_id: str, channel_id: str, *, cursor: str | None = None, limit: int = 5
    ) -> tuple[dict[str, Any], ...]:
        return await self._list_v1_metadata(
            f"/api/v1/communities/{community_id}/channels/{channel_id}/automod/alerts",
            cursor,
            limit,
        )

    async def _list_v1_metadata(
        self, path: str, cursor: str | None, limit: int
    ) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        payload = (
            await self._transport.request("GET", path, params={"cursor": cursor, "limit": limit})
            or {}
        )
        values = payload.get("items", ())
        return tuple(item for item in values if isinstance(item, dict))

    async def get(self, community_id: str) -> AutoModConfig:
        payload = await self._transport.request("GET", f"/api/communities/{community_id}/automod")
        raw_config = payload.get("config") if payload else None
        return AutoModConfig.from_dict(raw_config if isinstance(raw_config, dict) else {})

    async def update(self, community_id: str, config: AutoModConfig) -> AutoModConfig:
        normalized = _validate(config)
        payload = await self._transport.request(
            "PUT",
            f"/api/communities/{community_id}/automod",
            json=normalized.to_dict(),
        )
        raw_config = payload.get("config") if payload else None
        if not isinstance(raw_config, dict):
            raise RuntimeError("VoiceRoute returned no AutoMod configuration")
        return AutoModConfig.from_dict(raw_config)


def _validate(config: AutoModConfig) -> AutoModConfig:
    words = tuple(
        dict.fromkeys(unicodedata.normalize("NFC", word.strip()) for word in config.blocked_words)
    )
    if len(words) > 100 or any(not word or len(word) > 64 for word in words):
        raise ValueError("blocked_words must contain up to 100 non-empty words of 64 characters")
    limits = {
        "max_mentions": (config.max_mentions, 100),
        "spam_limit": (config.spam_limit, 30),
        "slowmode_seconds": (config.slowmode_seconds, 21600),
    }
    for name, (value, maximum) in limits.items():
        if isinstance(value, bool) or not 0 <= value <= maximum:
            raise ValueError(f"{name} must be between 0 and {maximum}")
    return AutoModConfig(
        enabled=config.enabled,
        blocked_words=words,
        max_mentions=config.max_mentions,
        spam_limit=config.spam_limit,
        block_duplicates=config.block_duplicates,
        slowmode_seconds=config.slowmode_seconds,
    )


def _validate_rule_name(name: str) -> None:
    if not name or len(name) > 100:
        raise ValueError("automatic moderation rule names must contain 1 to 100 characters")


def _rule_body(
    name: str,
    trigger: str,
    metadata: Mapping[str, Any],
    actions: Sequence[Mapping[str, Any]],
    enabled: bool,
    exempt_role_ids: Sequence[str],
    exempt_channel_ids: Sequence[str],
) -> dict[str, Any]:
    _validate_rule_name(name)
    if trigger not in {"KEYWORDS", "PRESET", "REGEX", "MENTION_SPAM", "LINK_POLICY"}:
        raise ValueError("unsupported automatic moderation trigger")
    if not 1 <= len(actions) <= 3:
        raise ValueError("automatic moderation rules require 1 to 3 actions")
    if len(exempt_role_ids) > 100 or len(set(exempt_role_ids)) != len(exempt_role_ids):
        raise ValueError("exempt_role_ids must contain at most 100 unique IDs")
    if len(exempt_channel_ids) > 50 or len(set(exempt_channel_ids)) != len(exempt_channel_ids):
        raise ValueError("exempt_channel_ids must contain at most 50 unique IDs")
    return {
        "name": name,
        "enabled": enabled,
        "trigger": trigger,
        "metadata": dict(metadata),
        "actions": [dict(action) for action in actions],
        "exemptRoleIds": list(exempt_role_ids),
        "exemptChannelIds": list(exempt_channel_ids),
    }


def _rule_object(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        raise RuntimeError("VoiceRoute returned no automatic moderation rule")
    value = payload.get("rule", payload)
    if not isinstance(value, dict):
        raise RuntimeError("VoiceRoute returned an invalid automatic moderation rule")
    return value
