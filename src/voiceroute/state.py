"""Bounded local state cache updated by Gateway signal events."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from voiceroute.models import PlatformEvent
from voiceroute.state_models import CachedEntity, EntityKind, cached_entity

if TYPE_CHECKING:
    from voiceroute.client import VoiceRouteClient


@dataclass(frozen=True, slots=True)
class CachePolicy:
    communities: bool = True
    channels: bool = True
    roles: bool = True
    members: bool = True
    threads: bool = True
    messages: bool = False
    categories: bool = True
    polls: bool = True
    expressions: bool = True
    bans: bool = True
    voice_states: bool = True
    installations: bool = True
    max_messages: int = 1_000
    max_per_domain: int = 10_000
    reconcile_on_ready: bool = False

    def __post_init__(self) -> None:
        if self.max_messages <= 0:
            raise ValueError("max_messages must be positive")
        if self.max_per_domain <= 0:
            raise ValueError("max_per_domain must be positive")


@dataclass(frozen=True, slots=True)
class CacheChange:
    event: PlatformEvent
    before: CachedEntity | None
    after: CachedEntity | None


@dataclass(slots=True)
class StateCache:
    policy: CachePolicy = field(default_factory=CachePolicy)
    _entities: dict[EntityKind, dict[str, CachedEntity]] = field(init=False)
    _orders: dict[EntityKind, OrderedDict[str, None]] = field(init=False)
    _changes: OrderedDict[str, CacheChange] = field(init=False)

    def __post_init__(self) -> None:
        self._entities = {
            "community": {},
            "category": {},
            "channel": {},
            "role": {},
            "member": {},
            "thread": {},
            "message": {},
            "poll": {},
            "expression": {},
            "ban": {},
            "voice_state": {},
            "installation": {},
        }
        self._orders = {kind: OrderedDict() for kind in self._entities}
        self._changes = OrderedDict()

    async def apply(self, event: PlatformEvent) -> None:
        descriptor = self._descriptor(event)
        if descriptor is None:
            return
        kind, entity_id, deleted = descriptor
        policy_name = {
            "community": "communities",
            "category": "categories",
        }.get(kind, f"{kind}s")
        if not getattr(self.policy, policy_name):
            return
        before = self._entities[kind].get(entity_id)
        if deleted:
            after = None
            self._entities[kind].pop(entity_id, None)
            self._orders[kind].pop(entity_id, None)
        else:
            merged = dict(before.data) if before is not None else {}
            merged.update(event.data)
            after = cached_entity(
                kind,
                entity_id,
                merged,
                sequence=event.sequence,
                community_id=self._string(event.data.get("communityId")),
                channel_id=self._string(event.data.get("channelId")),
                partial=True,
                redacted=bool(event.data.get("redacted", False)),
            )
            self._entities[kind][entity_id] = after
            self._orders[kind].pop(entity_id, None)
            self._orders[kind][entity_id] = None
            self._trim(kind)
        key = self._event_key(event)
        self._changes[key] = CacheChange(event, before, after)
        while len(self._changes) > 1_024:
            self._changes.popitem(last=False)

    def change_for(self, event: PlatformEvent) -> CacheChange | None:
        return self._changes.get(self._event_key(event))

    async def rollback(self, event: PlatformEvent) -> None:
        """Restore the snapshot that existed before a failed event handler."""
        change = self._changes.pop(self._event_key(event), None)
        if change is None:
            return
        descriptor = self._descriptor(event)
        if descriptor is None:
            return
        kind, entity_id, _ = descriptor
        if change.before is None:
            self._entities[kind].pop(entity_id, None)
            self._orders[kind].pop(entity_id, None)
            return
        self._entities[kind][entity_id] = change.before
        self._orders[kind].pop(entity_id, None)
        self._orders[kind][entity_id] = None

    def get_community(self, community_id: str) -> CachedEntity | None:
        return self._entities["community"].get(community_id)

    def get_channel(self, channel_id: str) -> CachedEntity | None:
        return self._entities["channel"].get(channel_id)

    def get_role(self, role_id: str) -> CachedEntity | None:
        return self._entities["role"].get(role_id)

    def get_member(self, community_id: str, user_id: str | int) -> CachedEntity | None:
        return self._entities["member"].get(f"{community_id}:{user_id}")

    def get_thread(self, thread_id: str) -> CachedEntity | None:
        return self._entities["thread"].get(thread_id)

    def get_message(
        self, community_id: str, channel_id: str, message_id_or_seq: str
    ) -> CachedEntity | None:
        return self._entities["message"].get(f"{community_id}:{channel_id}:{message_id_or_seq}")

    def get_cached(self, kind: EntityKind, entity_id: str) -> CachedEntity | None:
        return self._entities[kind].get(entity_id)

    async def reconcile(self, client: VoiceRouteClient) -> None:
        """Rebuild REST-readable state after a non-resumable Gateway gap."""
        self.clear()
        if not self.policy.communities:
            return
        for community in await client.communities.list():
            self.store(
                "community",
                community.id,
                {"id": community.id, "name": community.name},
                partial=False,
            )
            if self.policy.channels:
                for channel in await client.communities.list_channels(community.id):
                    self.store(
                        "channel",
                        channel.id,
                        {
                            "id": channel.id,
                            "communityId": community.id,
                            "name": channel.name,
                            "kind": channel.kind,
                            "categoryId": channel.category_id,
                            "position": channel.position,
                        },
                        partial=False,
                    )
            if self.policy.roles:
                for role in await client.roles.list(community.id):
                    self.store(
                        "role",
                        role.id,
                        {
                            "id": role.id,
                            "communityId": community.id,
                            "name": role.name,
                            "position": role.position,
                        },
                        partial=False,
                    )
            if self.policy.members:
                for member in await client.members.list(community.id):
                    self.store(
                        "member",
                        f"{community.id}:{member.id}",
                        {
                            "communityId": community.id,
                            "userId": str(member.id),
                            "displayName": member.display_name,
                            "roleIds": member.role_ids,
                        },
                        partial=False,
                    )

    def store(
        self,
        kind: EntityKind,
        entity_id: str,
        data: Mapping[str, Any],
        *,
        partial: bool,
        sequence: str | None = None,
    ) -> CachedEntity:
        payload = dict(data)
        entity = cached_entity(
            kind,
            entity_id,
            payload,
            sequence=sequence,
            community_id=self._string(data.get("communityId")),
            channel_id=self._string(data.get("channelId")),
            partial=partial,
            redacted=bool(data.get("redacted", False)),
        )
        self._entities[kind][entity_id] = entity
        self._orders[kind].pop(entity_id, None)
        self._orders[kind][entity_id] = None
        self._trim(kind)
        return entity

    def clear(self) -> None:
        for values in self._entities.values():
            values.clear()
        for order in self._orders.values():
            order.clear()
        self._changes.clear()

    def _descriptor(self, event: PlatformEvent) -> tuple[EntityKind, str, bool] | None:
        name = event.name
        kind: EntityKind | None = None
        if name.startswith("COMMUNITY_"):
            kind = "community"
        elif name.startswith("CATEGORY_"):
            kind = "category"
        elif name.startswith("CHANNEL_"):
            kind = "channel"
        elif name.startswith("ROLE_"):
            kind = "role"
        elif name.startswith("MEMBER_") or name == "PRESENCE_UPDATED":
            kind = "member"
        elif name.startswith("THREAD_") and not name.startswith("THREAD_MEMBER"):
            kind = "thread"
        elif name.startswith("MESSAGE_"):
            kind = "message"
        elif name.startswith("POLL_"):
            kind = "poll"
        elif name.startswith("EXPRESSION_"):
            kind = "expression"
        elif name.startswith("BAN_"):
            kind = "ban"
        elif name.startswith("VOICE_STATE_"):
            kind = "voice_state"
        elif name.startswith(("INSTALLATION_", "USER_INSTALLATION_")):
            kind = "installation"
        if kind is None:
            return None
        entity_id = self._entity_id(kind, event.data)
        if entity_id is None:
            return None
        deleted = name.endswith("_DELETED") or name == "MEMBER_LEFT"
        return kind, entity_id, deleted

    def _entity_id(self, kind: EntityKind, data: Mapping[str, Any]) -> str | None:
        if kind == "community":
            return self._string(data.get("id", data.get("communityId")))
        if kind == "channel":
            return self._string(data.get("id", data.get("channelId", data.get("categoryId"))))
        if kind == "category":
            return self._string(data.get("id", data.get("categoryId")))
        if kind == "role":
            return self._string(data.get("id", data.get("roleId")))
        if kind == "thread":
            return self._string(data.get("id", data.get("threadId")))
        if kind == "poll":
            return self._string(data.get("id", data.get("pollId")))
        if kind == "expression":
            return self._string(data.get("id", data.get("expressionId")))
        if kind == "ban":
            community_id = self._string(data.get("communityId"))
            user_id = self._string(data.get("userId"))
            return f"{community_id}:{user_id}" if community_id and user_id else None
        if kind == "voice_state":
            community_id = self._string(data.get("communityId"))
            user_id = self._string(data.get("userId"))
            return f"{community_id}:{user_id}" if community_id and user_id else None
        if kind == "installation":
            return self._string(data.get("id", data.get("installationId")))
        community_id = self._string(data.get("communityId"))
        if kind == "member":
            user_id = self._string(data.get("userId"))
            return f"{community_id}:{user_id}" if community_id and user_id else None
        channel_id = self._string(data.get("channelId"))
        message_id = self._string(data.get("messageId", data.get("messageSeq")))
        return (
            f"{community_id}:{channel_id}:{message_id}"
            if community_id and channel_id and message_id
            else None
        )

    def _trim(self, kind: EntityKind) -> None:
        limit = self.policy.max_messages if kind == "message" else self.policy.max_per_domain
        while len(self._orders[kind]) > limit:
            entity_id, _ = self._orders[kind].popitem(last=False)
            self._entities[kind].pop(entity_id, None)

    @staticmethod
    def _event_key(event: PlatformEvent) -> str:
        return event.delivery_id or f"{event.sequence}:{event.name}"

    @staticmethod
    def _string(value: Any) -> str | None:
        return None if value is None else str(value)
