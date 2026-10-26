"""Community audit log endpoint."""

from voiceroute.models import AuditPage
from voiceroute.transport import HTTPTransport


class AuditAPI:
    """Read immutable community audit entries with cursor pagination."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def list(
        self,
        community_id: str,
        *,
        before: str | None = None,
        action: str | None = None,
        actor_id: int | None = None,
        limit: int = 50,
    ) -> AuditPage:
        if before is not None and (
            not before.isdecimal()
            or before.startswith("0")
            or int(before) > 9_223_372_036_854_775_807
        ):
            raise ValueError("before must be a positive decimal cursor")
        if actor_id is not None and (
            isinstance(actor_id, bool) or not 1 <= actor_id <= 2_147_483_647
        ):
            raise ValueError("actor_id must be a positive 32-bit integer")
        if isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        payload = await self._transport.request(
            "GET",
            f"/api/communities/{community_id}/audit",
            params={"before": before, "action": action, "actorId": actor_id, "limit": limit},
        )
        return AuditPage.from_dict(payload or {})
