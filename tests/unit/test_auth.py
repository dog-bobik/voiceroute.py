import pytest

from voiceroute.transport.auth import BasicAuth, BearerAuth, BotAuth, CallbackTokenAuth


def test_bot_auth_builds_expected_header() -> None:
    auth = BotAuth("vrb_secret")

    assert auth.headers() == {"Authorization": "Bot vrb_secret"}
    assert "secret" not in repr(auth)


def test_bot_auth_rejects_non_bot_token() -> None:
    with pytest.raises(ValueError, match="vrb_"):
        BotAuth("not-a-bot-token")


def test_other_auth_strategies_redact_credentials() -> None:
    bearer = BearerAuth("oauth-secret")
    basic = BasicAuth("client", "secret")
    callback = CallbackTokenAuth("callback-secret")

    assert bearer.headers() == {"Authorization": "Bearer oauth-secret"}
    assert basic.headers()["Authorization"].startswith("Basic ")
    assert callback.headers() == {}
    assert callback.path_value() == "callback-secret"
    assert "oauth-secret" not in repr(bearer)
    assert repr(basic) == "BasicAuth(client_id=<redacted>, client_secret=<redacted>)"
    assert "callback-secret" not in repr(callback)
