"""V1 poll lifecycle, ballot, and results endpoints."""

from __future__ import annotations

import uuid

from voiceroute.models import Poll, PollCreation, PollVoter, PollVoterPage, RichMessage
from voiceroute.transport import HTTPTransport


class PollsAPI:
    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def create(
        self,
        community_id: str,
        channel_id: str,
        question: str,
        answers: tuple[str, ...],
        *,
        duration_seconds: int,
        multiple: bool = False,
        anonymous: bool = False,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> PollCreation:
        if not question or len(question) > 300:
            raise ValueError("question must contain between 1 and 300 characters")
        if not 2 <= len(answers) <= 10 or any(not a or len(a) > 100 for a in answers):
            raise ValueError("polls require 2 to 10 answers, each 1 to 100 characters")
        if not 60 <= duration_seconds <= 604800:
            raise ValueError("duration_seconds must be between 60 and 604800")
        payload = await self._transport.request(
            "POST",
            _polls_path(community_id, channel_id),
            json={
                "question": question,
                "answers": list(answers),
                "durationSeconds": duration_seconds,
                "multiple": multiple,
                "anonymous": anonymous,
            },
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        data = payload or {}
        poll = data.get("poll")
        message = data.get("message")
        if not isinstance(poll, dict) or not isinstance(message, dict):
            raise RuntimeError("VoiceRoute returned an invalid poll creation response")
        return PollCreation(Poll.from_dict(poll), RichMessage.from_dict(message))

    async def get(self, community_id: str, channel_id: str, poll_id: str) -> Poll:
        payload = await self._transport.request(
            "GET", f"{_poll_path(community_id, channel_id, poll_id)}"
        )
        return Poll.from_dict(_required_poll(payload))

    async def vote(
        self,
        community_id: str,
        channel_id: str,
        poll_id: str,
        answer_ids: tuple[str, ...],
        *,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Poll:
        if len(answer_ids) > 10 or len(set(answer_ids)) != len(answer_ids):
            raise ValueError("answer_ids must contain at most 10 unique IDs")
        payload = await self._transport.request(
            "PUT",
            f"{_poll_path(community_id, channel_id, poll_id)}/votes/@me",
            json={"answerIds": list(answer_ids)},
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return Poll.from_dict(_required_poll(payload))

    async def remove_vote(
        self,
        community_id: str,
        channel_id: str,
        poll_id: str,
        *,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Poll:
        payload = await self._transport.request(
            "DELETE",
            f"{_poll_path(community_id, channel_id, poll_id)}/votes/@me",
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            retryable=True,
        )
        return Poll.from_dict(_required_poll(payload))

    async def close(
        self,
        community_id: str,
        channel_id: str,
        poll_id: str,
        *,
        if_match: str,
        reason: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Poll:
        if reason is not None and len(reason) > 512:
            raise ValueError("reason cannot exceed 512 characters")
        payload = await self._transport.request(
            "POST",
            f"{_poll_path(community_id, channel_id, poll_id)}/close",
            json={"reason": reason} if reason is not None else {},
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
        )
        return Poll.from_dict(_required_poll(payload))

    async def voters(
        self,
        community_id: str,
        channel_id: str,
        poll_id: str,
        *,
        cursor: str | None = None,
        answer_id: str | None = None,
        limit: int = 50,
    ) -> PollVoterPage:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        payload = await self._transport.request(
            "GET",
            f"{_poll_path(community_id, channel_id, poll_id)}/voters",
            params={"cursor": cursor, "answerId": answer_id, "limit": limit},
        )
        data = payload or {}
        values = data.get("items", ())
        items = values if isinstance(values, list) else []
        next_cursor = data.get("nextCursor")
        return PollVoterPage(
            tuple(PollVoter.from_dict(item) for item in items if isinstance(item, dict)),
            str(next_cursor) if next_cursor is not None else None,
        )


def _polls_path(community_id: str, channel_id: str) -> str:
    return f"/api/v1/communities/{community_id}/channels/{channel_id}/polls"


def _poll_path(community_id: str, channel_id: str, poll_id: str) -> str:
    return f"{_polls_path(community_id, channel_id)}/{poll_id}"


def _required_poll(payload: dict[str, object] | None) -> dict[str, object]:
    if payload is None:
        raise RuntimeError("VoiceRoute returned no poll")
    raw = payload.get("poll", payload)
    if not isinstance(raw, dict):
        raise RuntimeError("VoiceRoute returned an invalid poll")
    return raw
