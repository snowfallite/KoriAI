"""Seed fixtures (tech.md §15.2): the seed, the fakes and the tests read the same files."""

import csv
from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter

# backend/fixtures/seed; the API image keeps it at /app/fixtures/seed.
SEED = Path(__file__).resolve().parents[2] / "fixtures" / "seed"


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load[T](path: Path, adapter: TypeAdapter[T]) -> T:
    """A fixture file validated by its contract model."""
    return adapter.validate_python(read_yaml(path))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as rows:
        return list(csv.DictReader(rows))
