"""Incremental Server-Sent Events decoding."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SSEEvent:
    """One decoded SSE frame."""

    event: str
    data: str
    id: str | None = None
    retry: int | None = None


class SSEDecoder:
    """Decode SSE fields one line at a time according to the event-stream format."""

    def __init__(self) -> None:
        self._event = "message"
        self._data: list[str] = []
        self._id: str | None = None
        self._retry: int | None = None

    def feed_line(self, line: str) -> SSEEvent | None:
        if line == "":
            return self._dispatch()
        if line.startswith(":"):
            return None

        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]

        if field == "event":
            self._event = value
        elif field == "data":
            self._data.append(value)
        elif field == "id" and "\x00" not in value:
            self._id = value
        elif field == "retry":
            try:
                self._retry = int(value)
            except ValueError:
                pass
        return None

    def _dispatch(self) -> SSEEvent | None:
        if not self._data:
            self._event = "message"
            self._retry = None
            return None

        event = SSEEvent(
            event=self._event,
            data="\n".join(self._data),
            id=self._id,
            retry=self._retry,
        )
        self._event = "message"
        self._data = []
        self._retry = None
        return event
