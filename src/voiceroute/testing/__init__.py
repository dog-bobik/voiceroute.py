"""Deterministic helpers for SDK consumers testing without a live server."""

from voiceroute.testing.fakes import FakeGatewaySocket, FakeTransport, RecordedRequest

__all__ = ["FakeGatewaySocket", "FakeTransport", "RecordedRequest"]
