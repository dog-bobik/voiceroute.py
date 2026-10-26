"""VoiceRoute community permission values and immutable sets."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from enum import StrEnum
from typing import Self


class Permission(StrEnum):
    """Permission names defined by the current VoiceRoute server contract."""

    VIEW_CHANNEL = "viewChannel"
    READ_MESSAGE_HISTORY = "readMessageHistory"
    SEND_MESSAGES = "sendMessages"
    ATTACH_FILES = "attachFiles"
    ADD_REACTIONS = "addReactions"
    MANAGE_MESSAGES = "manageMessages"
    CREATE_PUBLIC_THREADS = "createPublicThreads"
    CREATE_PRIVATE_THREADS = "createPrivateThreads"
    SEND_MESSAGES_IN_THREADS = "sendMessagesInThreads"
    MANAGE_THREADS = "manageThreads"
    CONNECT = "connect"
    SPEAK = "speak"
    STREAM = "stream"
    LISTEN = "listen"
    USE_APPLICATION_COMMANDS = "useApplicationCommands"
    MENTION_EVERYONE = "mentionEveryone"
    MUTE_MEMBERS = "muteMembers"
    DEAFEN_MEMBERS = "deafenMembers"
    MOVE_MEMBERS = "moveMembers"
    MANAGE_CHANNELS = "manageChannels"
    MANAGE_ROLES = "manageRoles"
    MANAGE_COMMUNITY = "manageCommunity"
    CREATE_INVITES = "createInvites"
    KICK_MEMBERS = "kickMembers"
    BAN_MEMBERS = "banMembers"
    MODERATE_MEMBERS = "moderateMembers"
    CHANGE_NICKNAME = "changeNickname"
    MANAGE_NICKNAMES = "manageNicknames"
    VIEW_AUDIT_LOG = "viewAuditLog"
    MANAGE_STAGE = "manageStage"
    REQUEST_TO_SPEAK = "requestToSpeak"
    MANAGE_EXPRESSIONS = "manageExpressions"
    USE_SOUNDBOARD = "useSoundboard"
    ADMINISTRATOR = "administrator"


ALL_PERMISSIONS = frozenset(Permission)


class Permissions:
    """Immutable, type-safe effective permission set."""

    __slots__ = ("_values",)

    def __init__(self, values: Iterable[Permission | str] = ()) -> None:
        normalized = frozenset(Permission(value) for value in values)
        self._values = ALL_PERMISSIONS if Permission.ADMINISTRATOR in normalized else normalized

    @classmethod
    def all(cls) -> Self:
        return cls(ALL_PERMISSIONS)

    def has(self, permission: Permission | str) -> bool:
        return Permission(permission) in self._values

    def has_all(self, permissions: Iterable[Permission | str]) -> bool:
        return all(self.has(permission) for permission in permissions)

    def has_any(self, permissions: Iterable[Permission | str]) -> bool:
        return any(self.has(permission) for permission in permissions)

    def missing(self, permissions: Iterable[Permission | str]) -> tuple[Permission, ...]:
        required = tuple(Permission(permission) for permission in permissions)
        return tuple(permission for permission in required if permission not in self._values)

    def to_values(self) -> tuple[str, ...]:
        return tuple(permission.value for permission in Permission if permission in self._values)

    def __contains__(self, permission: object) -> bool:
        try:
            return Permission(permission) in self._values  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False

    def __iter__(self) -> Iterator[Permission]:
        return (permission for permission in Permission if permission in self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __bool__(self) -> bool:
        return bool(self._values)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Permissions):
            return self._values == other._values
        if isinstance(other, (tuple, list, set, frozenset)):
            try:
                return self._values == frozenset(Permission(value) for value in other)
            except (TypeError, ValueError):
                return False
        return False

    def __repr__(self) -> str:
        values = ", ".join(repr(value) for value in self.to_values())
        return f"Permissions([{values}])"
