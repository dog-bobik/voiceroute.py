"""Deterministic helpers for SDK consumers testing without a live server."""

from voiceroute.testing.fakes import FakeTransport, RecordedRequest

__all__ = ["FakeTransport", "RecordedRequest"]
