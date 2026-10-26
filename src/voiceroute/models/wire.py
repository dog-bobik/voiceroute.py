"""Forward-compatible primitives used by generated Bot Platform wire models."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, TypeGuard


class _UnsetType:
    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET: Final = _UnsetType()
"""Value used to distinguish an omitted field from an explicit JSON ``null``."""

UnsetType = _UnsetType


def is_set(value: object) -> TypeGuard[object]:
    """Return ``False`` only for the omission sentinel."""
    return value is not UNSET


@dataclass(frozen=True, slots=True)
class OpenEnumValue:
    """An enum-like string that preserves values introduced by newer servers."""

    value: str
    known: bool

    @classmethod
    def parse(cls, value: object, known_values: frozenset[str]) -> OpenEnumValue:
        if not isinstance(value, str):
            raise TypeError("enum wire value must be a string")
        return cls(value=value, known=value in known_values)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class WireObject:
    """Raw object storage that keeps unknown optional fields for round trips."""

    values: Mapping[str, Any]
    additional_properties: Mapping[str, Any]

    @classmethod
    def parse(cls, data: Mapping[str, Any], known_fields: frozenset[str]) -> WireObject:
        values = {key: value for key, value in data.items() if key in known_fields}
        additional = {key: value for key, value in data.items() if key not in known_fields}
        return cls(MappingProxyType(values), MappingProxyType(additional))

    def to_dict(self) -> dict[str, Any]:
        return {**self.additional_properties, **self.values}


_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def camel_to_snake(value: str) -> str:
    """Apply the stable generated-model naming policy."""
    return _CAMEL_BOUNDARY.sub("_", value).replace("-", "_").lower()
