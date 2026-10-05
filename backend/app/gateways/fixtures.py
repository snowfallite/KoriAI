"""Seed fixtures (tech.md §15.2): the seed, the fakes and the tests read the same files."""

import csv
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, SecretStr, TypeAdapter

# backend/fixtures/seed; the API image keeps it at /app/fixtures/seed.
SEED = Path(__file__).resolve().parents[2] / "fixtures" / "seed"


class SeedUser(BaseModel):
    """A row of seed/users.yaml. Every seed user signs in with SEED_OWNER_PASSWORD; the owner
    takes the address of SEED_OWNER_EMAIL."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    email: str
    role: Literal["user", "owner"]  # users.role (§5.1)
    display_name: str | None = None
    # A made-up token of the broker connection: only the T-Invest fake answers to it.
    broker_token: SecretStr | None = None


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load[T](path: Path, adapter: TypeAdapter[T]) -> T:
    """A fixture file validated by its contract model."""
    return adapter.validate_python(read_yaml(path))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as rows:
        return list(csv.DictReader(rows))


def seed_users() -> list[SeedUser]:
    return load(SEED / "users.yaml", TypeAdapter(list[SeedUser]))
