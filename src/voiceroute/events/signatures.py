"""Verification helpers for signed durable webhook deliveries."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping
from importlib import import_module
from typing import Any, Protocol

_HEADER_PREFIX = "x-voiceroute-"
_HEX_64 = re.compile(r"^[0-9a-fA-F]{128}$")


class DeliveryReplayStore(Protocol):
    """Atomic one-time delivery ID store with expiry."""

    async def claim(self, delivery_id: str, *, expires_at: int) -> bool:
        """Return true only when this delivery ID was not already claimed."""
        ...


class InvalidDeliverySignature(ValueError):
    """Raised for malformed, stale, unknown-key, or invalid signed deliveries."""


async def verify_signed_delivery(
    raw_body: bytes,
    headers: Mapping[str, str],
    public_keys: Mapping[str, str | bytes],
    replay_store: DeliveryReplayStore,
    *,
    now: int | None = None,
    allowed_clock_skew_seconds: int = 300,
    max_body_bytes: int = 524_288,
) -> dict[str, Any]:
    """Verify exact raw bytes before parsing, then claim the stable delivery ID.

    ``public_keys`` must be loaded from an already trusted VoiceRoute origin and
    keyed by key ID. This helper never fetches a key based on untrusted headers.
    Install the optional ``webhooks`` extra for Ed25519 support.
    """
    if allowed_clock_skew_seconds < 0:
        raise ValueError("allowed_clock_skew_seconds cannot be negative")
    if max_body_bytes <= 0:
        raise ValueError("max_body_bytes must be positive")
    if len(raw_body) > max_body_bytes:
        raise InvalidDeliverySignature("signed delivery body exceeds the configured size limit")
    normalized = {name.lower(): value for name, value in headers.items()}
    signature = normalized.get(f"{_HEADER_PREFIX}signature", "")
    timestamp = normalized.get(f"{_HEADER_PREFIX}timestamp", "")
    delivery_id = normalized.get(f"{_HEADER_PREFIX}delivery-id", "")
    key_id = normalized.get(f"{_HEADER_PREFIX}key-id", "")
    if (
        not timestamp.isdecimal()
        or not delivery_id
        or not key_id
        or not _HEX_64.fullmatch(signature)
    ):
        raise InvalidDeliverySignature("missing or malformed VoiceRoute signature headers")
    timestamp_value = int(timestamp)
    current = int(time.time()) if now is None else now
    if abs(current - timestamp_value) > allowed_clock_skew_seconds:
        raise InvalidDeliverySignature("signed delivery timestamp is outside the allowed window")
    encoded_key = public_keys.get(key_id)
    if encoded_key is None:
        raise InvalidDeliverySignature("unknown VoiceRoute signing key")
    try:
        key_bytes = bytes.fromhex(encoded_key) if isinstance(encoded_key, str) else encoded_key
        signed_data = f"{timestamp}.{delivery_id}.".encode() + raw_body
        _verify_ed25519(key_bytes, bytes.fromhex(signature), signed_data)
    except InvalidDeliverySignature:
        raise
    except (ImportError, ValueError, TypeError) as exc:
        raise InvalidDeliverySignature("invalid VoiceRoute Ed25519 signature") from exc

    try:
        envelope = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidDeliverySignature("signed delivery body is not valid JSON") from exc
    if not isinstance(envelope, dict) or envelope.get("deliveryId") != delivery_id:
        raise InvalidDeliverySignature("header and envelope delivery IDs do not match")
    if not await replay_store.claim(
        delivery_id, expires_at=current + allowed_clock_skew_seconds
    ):
        raise InvalidDeliverySignature("delivery ID has already been processed")
    return envelope


def _verify_ed25519(public_key: bytes, signature: bytes, message: bytes) -> None:
    if len(public_key) != 32 or len(signature) != 64:
        raise ValueError("Ed25519 public key or signature has an invalid size")
    crypto_exceptions = import_module("cryptography.exceptions")
    ed25519 = import_module("cryptography.hazmat.primitives.asymmetric.ed25519")
    try:
        ed25519.Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
    except crypto_exceptions.InvalidSignature as exc:
        raise ValueError("Ed25519 signature verification failed") from exc
