"""Community and channel endpoints available to bots."""

from __future__ import annotations

import builtins

from voiceroute.models import Channel, Community
from voiceroute.transport import HTTPTransport


class CommunitiesAPI:
    """Read communities and their bot-visible channels."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def list(self) -> list[Community]:
        payload = await self._transport.request("GET", "/api/communities")
        if payload is None:
            return []
        return [Community.from_dict(item) for item in payload.get("items", [])]

    async def get(self, community_id: str) -> Community:
        payload = await self._transport.request("GET", f"/api/communities/{community_id}")
        if payload is None:
            raise RuntimeError("VoiceRoute returned no community")
        data = payload.get("community", payload)
        return Community.from_dict(data)

    async def list_channels(self, community_id: str) -> builtins.list[Channel]:
        payload = await self._transport.request("GET", f"/api/communities/{community_id}/channels")
        if payload is None:
            return []
        return [
            Channel.from_dict(item, community_id=community_id) for item in payload.get("items", [])
        ]
