"""Application settings: the only config module (tech.md §15.3)."""

import base64
from datetime import date
from pathlib import Path
from typing import Annotated, Literal, Self, get_args

from pydantic import BeforeValidator, SecretBytes, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.contracts.llm import ModelFamily

Mode = Literal["fake", "real"]


def _split(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_pairs(raw: str) -> dict[str, str]:
    pairs = {}
    for item in _split(raw):
        key, sep, value = item.partition(":")
        if not sep:
            # No item in the message: the value may be a secret.
            raise ValueError("expected comma-separated key:value pairs")
        pairs[key.strip()] = value.strip()
    return pairs


def _items(raw: object) -> object:
    return _split(raw) if isinstance(raw, str) else raw


def _pairs(raw: object) -> object:
    return _parse_pairs(raw) if isinstance(raw, str) else raw


def _aes_keys(raw: object) -> object:
    if not isinstance(raw, str):
        return raw
    keys = {kid: base64.b64decode(value, validate=True) for kid, value in _parse_pairs(raw).items()}
    if any(len(key) != 32 for key in keys.values()):
        raise ValueError("AES-256-GCM keys must decode to 32 bytes")
    return keys


# Env values of lists and maps: "a,b" and "k:v,k:v".
Items = BeforeValidator(_items)
Pairs = BeforeValidator(_pairs)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
        enable_decoding=False,
        env_ignore_empty=True,
        # Startup errors must not print secret values.
        hide_input_in_errors=True,
    )

    # App
    APP_ENV: Literal["dev", "ci", "staging", "prod"] = "dev"
    APP_BASE_URL: str = "http://localhost:5173"
    APP_ALLOWED_ORIGINS: Annotated[tuple[str, ...], Items] = ("http://localhost:5173",)
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    DATA_DIR: Path = Path("/data")
    JOBS_ENABLED: bool = True

    # DB
    DATABASE_URL: SecretStr = SecretStr("postgresql+psycopg://app:app@localhost:5432/app")
    DB_POOL_SIZE: int = 10

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: SecretStr = SecretStr("")
    QDRANT_COLLECTION: str = "doc_chunks"

    # Auth
    SESSION_TTL_DAYS: int = 30
    COOKIE_SECURE: bool = False
    REGISTRATION_MODE: Literal["open", "invite", "closed"] = "invite"
    SEED_OWNER_EMAIL: str = "owner@example.test"
    SEED_OWNER_PASSWORD: SecretStr = SecretStr("")

    # T-Invest
    TINVEST_MODE: Mode = "fake"
    TINVEST_APP_NAME: str = "kori"
    TINVEST_SYSTEM_TOKEN: SecretStr = SecretStr("")
    TINVEST_TOKEN_KEYS: Annotated[dict[str, SecretBytes], BeforeValidator(_aes_keys)] = {}
    TINVEST_TOKEN_ACTIVE_KEY: str = "k1"  # noqa: S105 - a key id, not a key
    TINVEST_TIMEOUT_S: float = 20

    # LLM
    LLM_MODE: Mode = "fake"
    GIGACHAT_CREDENTIALS: SecretStr = SecretStr("")
    GIGACHAT_SCOPE: str = "GIGACHAT_API_PERS"
    GIGACHAT_BASE_URL: str = "https://api.giga.chat/v1"
    GIGACHAT_CA_BUNDLE: Path = Path("/app/certs/russian_trusted_root_ca.pem")
    GIGACHAT_TIMEOUT_S: float = 120
    LLM_MAX_CONCURRENCY: int = 1
    LLM_QUEUE_TIMEOUT_S: float = 90
    LLM_MODELS: Annotated[dict[ModelFamily, str], Pairs] = {
        "lite": "GigaChat-2",
        "pro": "GigaChat-2-Pro",
        "max": "GigaChat-2-Max",
        "ultra": "GigaChat-3-Ultra",
    }
    LLM_TOOLS_UNSUPPORTED: Annotated[frozenset[ModelFamily], Items] = frozenset()
    LLM_CONTEXT_TOKENS: Annotated[dict[ModelFamily, int], Pairs] = {
        "lite": 32000,
        "pro": 32000,
        "max": 32000,
        "ultra": 32000,
    }

    # Quotas
    LLM_QUOTAS: Annotated[dict[ModelFamily, int], Pairs] = {
        "lite": 250_000_000,
        "pro": 40_000_000,
        "max": 25_000_000,
        "ultra": 50_000_000,
    }
    LLM_QUOTA_PERIOD_START: date = date(2026, 9, 26)
    LLM_QUOTA_PERIOD_DAYS: int = 365
    LLM_PACE_MAX: float = 1.15
    LLM_PACE_GRACE_DAYS: int = 7
    LLM_RESERVE_PCT: float = 1
    USER_DAILY_BUDGET_LITE_EQ: int = 600_000
    BACKGROUND_DAILY_BUDGET_LITE_EQ: int = 1_500_000

    # Agent
    AGENT_HISTORY_MESSAGES: int = 8
    AGENT_RUN_TIMEOUT_S: float = 240
    AGENT_RUN_BUDGET_LITE_EQ: int = 400_000
    TOOL_TIMEOUT_S: float = 60
    RUN_EVENTS_TTL_S: float = 600

    # Web
    WEB_MODE: Mode = "fake"
    TAVILY_API_KEY: SecretStr = SecretStr("")
    TAVILY_MONTHLY_CREDITS: int = 1000
    TAVILY_USER_DAILY_CREDITS: int = 40
    WEB_CACHE_TTL_SEARCH_S: int = 21600
    WEB_CACHE_TTL_EXTRACT_S: int = 604800

    # Disclosures
    DISCLOSURE_MODE: Mode = "fake"
    EDISCLOSURE_BASE_URL: str = "https://www.e-disclosure.ru"
    EDISCLOSURE_RPS: float = 0.5
    DISCLOSURE_YEARS_BACK: int = 5

    # Vectors
    EMBEDDINGS_MODE: Mode = "fake"
    EMBEDDINGS_DENSE_MODEL: str = "intfloat/multilingual-e5-small"
    EMBEDDINGS_SPARSE_MODEL: str = "Qdrant/bm25"
    FASTEMBED_CACHE_DIR: Path = Path("/data/fastembed")
    VECTORS_MODE: Literal["memory", "qdrant"] = "memory"

    # Media
    FETCH_MODE: Mode = "fake"
    MEDIA_MAX_BYTES: int = 5_242_880

    # Fakes
    FAKE_FAULTS: Path | None = None
    FAKE_STRICT: bool = False

    # The SPA build reads it; declared so one .env serves both sides.
    PUBLIC_KITCHEN_SINK: bool = False

    @field_validator("LLM_MODELS", "LLM_CONTEXT_TOKENS", "LLM_QUOTAS")
    @classmethod
    def _cover_all_families(cls, value: dict[str, object]) -> dict[str, object]:
        if missing := set(get_args(ModelFamily)) - value.keys():
            raise ValueError(f"missing model families: {', '.join(sorted(missing))}")
        return value

    @model_validator(mode="after")
    def _check_environment(self) -> Self:
        errors = []
        # memory is the fake of Qdrant (§8.6).
        fakes = [
            name for name, value in self if name.endswith("_MODE") and value in {"fake", "memory"}
        ]
        if self.APP_ENV == "prod" and fakes:
            errors.append(f"APP_ENV=prod forbids fakes: {', '.join(fakes)}")
        if self.APP_ENV in {"staging", "prod"} and not self.COOKIE_SECURE:
            errors.append(f"APP_ENV={self.APP_ENV} requires COOKIE_SECURE=true")
        if self.FAKE_FAULTS is not None and self.APP_ENV not in {"dev", "ci"}:
            errors.append("FAKE_FAULTS works only in dev and ci")
        keys = self.TINVEST_TOKEN_KEYS
        if keys and self.TINVEST_TOKEN_ACTIVE_KEY not in keys:
            errors.append("TINVEST_TOKEN_ACTIVE_KEY is not in TINVEST_TOKEN_KEYS")
        if errors:
            raise ValueError("; ".join(errors))
        return self
