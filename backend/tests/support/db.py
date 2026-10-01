"""Throwaway databases on the dev or CI Postgres (tech.md §14.3)."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import Settings

BACKEND = Path(__file__).parents[2]
# Defaults only: model_construct reads neither the environment nor .env.
SERVER = make_url(Settings.model_construct().DATABASE_URL.get_secret_value())


@contextmanager
def scratch_database() -> Iterator[str]:
    """An empty database on the dev or CI Postgres, dropped afterwards."""
    name = f"kori_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(SERVER, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"create database {name}"))
    try:
        yield SERVER.set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f"drop database {name} with (force)"))
        admin.dispose()


def alembic_config(url: str) -> Config:
    config = Config(BACKEND / "alembic.ini")
    config.attributes["database_url"] = url
    return config
