"""Bot runtime lifecycle state."""

from enum import StrEnum


class RuntimeState(StrEnum):
    """Observable lifecycle state of a Bot instance."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    CLOSED = "closed"
