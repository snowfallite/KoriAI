"""Config validation: S1-02 AC 2 and 3, tech.md §15.3."""

import base64
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.config import Settings

AES_KEY = base64.b64encode(bytes(range(32))).decode()
REAL_CLIENTS = {
    "TINVEST_MODE": "real",
    "LLM_MODE": "real",
    "WEB_MODE": "real",
    "DISCLOSURE_MODE": "real",
    "EMBEDDINGS_MODE": "real",
    "VECTORS_MODE": "qdrant",
    "FETCH_MODE": "real",
}


def settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_env_example_lists_every_key_with_its_default() -> None:
    example = Path(__file__).parents[4] / ".env.example"
    lines = example.read_text(encoding="utf-8").splitlines()

    keys = {line.partition("=")[0] for line in lines if line and not line.startswith("#")}

    assert keys == set(Settings.model_fields)
    assert Settings(_env_file=example) == settings()


def test_defaults_start_dev_on_fakes() -> None:
    config = settings()

    assert config.APP_ENV == "dev"
    assert config.LLM_MODELS["ultra"] == "GigaChat-3-Ultra"
    assert config.LLM_QUOTAS["pro"] == 40_000_000


def test_env_file_lists_and_maps_parse(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "APP_ALLOWED_ORIGINS=https://a.example, https://b.example\n"
        "LLM_MODELS=lite:L,pro:P,max:M,ultra:U\n"
        "LLM_TOOLS_UNSUPPORTED=lite,pro\n"
        f"TINVEST_TOKEN_KEYS=k1:{AES_KEY},k2:{AES_KEY}\n"
        "QDRANT_API_KEY=\n",
        encoding="utf-8",
    )

    config = Settings(_env_file=env)

    assert config.APP_ALLOWED_ORIGINS == ("https://a.example", "https://b.example")
    assert config.LLM_MODELS == {"lite": "L", "pro": "P", "max": "M", "ultra": "U"}
    assert {"lite", "pro"} == config.LLM_TOOLS_UNSUPPORTED
    assert config.TINVEST_TOKEN_KEYS["k2"].get_secret_value() == bytes(range(32))
    assert config.QDRANT_API_KEY.get_secret_value() == ""


def test_unknown_env_file_key_fails_without_echoing_its_value(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("APP_ENV=dev\nGIGACHAT_CREDENTIAL=s3cr3t-value\n", encoding="utf-8")

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=env)

    assert "gigachat_credential" in str(error.value).lower()
    assert "s3cr3t-value" not in str(error.value)


@pytest.mark.parametrize("mode", REAL_CLIENTS)
def test_prod_rejects_every_fake(mode: str) -> None:
    fake = "memory" if mode == "VECTORS_MODE" else "fake"

    with pytest.raises(ValidationError, match=mode):
        settings(APP_ENV="prod", COOKIE_SECURE=True, **{**REAL_CLIENTS, mode: fake})


def test_prod_starts_on_real_clients() -> None:
    assert settings(APP_ENV="prod", COOKIE_SECURE=True, **REAL_CLIENTS).APP_ENV == "prod"


@pytest.mark.parametrize("app_env", ["staging", "prod"])
def test_staging_and_prod_require_secure_cookie(app_env: str) -> None:
    with pytest.raises(ValidationError, match="COOKIE_SECURE"):
        settings(APP_ENV=app_env, **REAL_CLIENTS)


def test_staging_allows_fakes() -> None:
    assert settings(APP_ENV="staging", COOKIE_SECURE=True).TINVEST_MODE == "fake"


def test_fault_plans_only_in_dev_and_ci() -> None:
    assert Path("faults.yaml") == settings(APP_ENV="ci", FAKE_FAULTS="faults.yaml").FAKE_FAULTS

    with pytest.raises(ValidationError, match="FAKE_FAULTS"):
        settings(APP_ENV="staging", COOKIE_SECURE=True, FAKE_FAULTS="faults.yaml")


def test_model_maps_cover_every_family() -> None:
    with pytest.raises(ValidationError, match="ultra"):
        settings(LLM_QUOTAS="lite:1,pro:2,max:3")


@pytest.mark.parametrize(
    "keys",
    ["k1:not~base64", f"k1:{base64.b64encode(bytes(16)).decode()}", f"{AES_KEY}"],
)
def test_token_keys_must_be_aes_256_without_echoing_them(keys: str) -> None:
    with pytest.raises(ValidationError) as error:
        settings(TINVEST_TOKEN_KEYS=keys)

    assert keys.removeprefix("k1:") not in str(error.value)


def test_active_token_key_must_exist() -> None:
    with pytest.raises(ValidationError, match="TINVEST_TOKEN_ACTIVE_KEY"):
        settings(TINVEST_TOKEN_KEYS=f"k2:{AES_KEY}")
