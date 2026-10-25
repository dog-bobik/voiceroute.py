"""Client configuration."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """Immutable network configuration for a VoiceRoute client."""

    base_url: str = "https://voiceroute.cc"
    timeout: float = 30.0

    def __post_init__(self) -> None:
        if not self.base_url.startswith(("https://", "http://")):
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))
