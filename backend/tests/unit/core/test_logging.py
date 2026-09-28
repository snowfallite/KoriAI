"""Secret redaction in logs: S1-02 AC 4, tech.md §3.5."""

import json

import pytest
import structlog

from app.core.logging import configure_logging, redact_secrets


@pytest.mark.parametrize(
    "key",
    [
        "token",
        "password",
        "authorization",
        "secret",
        "cookie",
        "sid",
        "credentials",
        "access_token",
        "new_password",
        "Set-Cookie",
        "GIGACHAT_CREDENTIALS",
        "TAVILY_API_KEY",
        "TINVEST_TOKEN_KEYS",
    ],
)
def test_secret_keys_are_masked(key: str) -> None:
    assert redact_secrets(None, "info", {key: "value"}) == {key: "***"}


@pytest.mark.parametrize(
    "key", ["prompt_tokens", "tokens_billable", "precached_tokens", "inside", "route"]
)
def test_other_keys_pass(key: str) -> None:
    assert redact_secrets(None, "info", {key: 12}) == {key: 12}


def test_nested_secrets_are_masked() -> None:
    event = {"request": {"headers": {"Authorization": "Bearer x"}, "items": [{"password": "p"}]}}

    assert redact_secrets(None, "info", event) == {
        "request": {"headers": {"Authorization": "***"}, "items": [{"password": "***"}]}
    }


def test_token_field_is_logged_as_stars(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")

    structlog.get_logger().info("broker_connected", token="t.secret-value", prompt_tokens=12)

    out = capsys.readouterr().out
    line = json.loads(out)
    assert line["token"] == "***"
    assert line["prompt_tokens"] == 12
    assert (line["event"], line["level"]) == ("broker_connected", "info")
    assert line["ts"].endswith("Z")
    assert "t.secret-value" not in out
