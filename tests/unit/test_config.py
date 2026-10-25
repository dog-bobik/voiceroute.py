import pytest

from voiceroute.config import ClientConfig


def test_config_normalizes_base_url() -> None:
    config = ClientConfig(base_url="https://dev.voiceroute.cc/")

    assert config.base_url == "https://dev.voiceroute.cc"


@pytest.mark.parametrize("base_url", ["", "dev.voiceroute.cc", "ftp://voiceroute.cc"])
def test_config_rejects_non_http_url(base_url: str) -> None:
    with pytest.raises(ValueError, match="absolute"):
        ClientConfig(base_url=base_url)
