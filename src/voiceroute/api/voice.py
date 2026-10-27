"""Bot-compatible VoiceRoute voice state resources."""

from voiceroute.models.voice import VoiceState, VoiceStatePage
from voiceroute.transport import HTTPTransport


class VoiceAPI:
    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def list_states(
        self,
        community_id: str,
        *,
        cursor: str | None = None,
        limit: int = 100,
    ) -> VoiceStatePage:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        payload = await self._transport.request(
            "GET",
            f"/api/v1/communities/{community_id}/voice-states",
            params={"cursor": cursor, "limit": limit},
        )
        data = payload or {}
        return VoiceStatePage(
            items=tuple(VoiceState.from_dict(item) for item in data.get("items", ())),
            next_cursor=(str(data["nextCursor"]) if data.get("nextCursor") is not None else None),
        )

    async def find_member_channel(self, community_id: str, user_id: int) -> str | None:
        cursor: str | None = None
        visited: set[str] = set()
        while True:
            page = await self.list_states(community_id, cursor=cursor)
            state = next(
                (
                    item
                    for item in page.items
                    if item.user_id == user_id
                    and item.channel_id is not None
                    and item.status != "DISCONNECTED"
                ),
                None,
            )
            if state is not None:
                return state.channel_id
            cursor = page.next_cursor
            if cursor is None or cursor in visited:
                return None
            visited.add(cursor)
