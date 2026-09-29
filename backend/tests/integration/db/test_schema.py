"""Schema and migrations (S1-03 AC 1-5), checked against the tech.md §5 DDL itself."""

import re
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Executable, create_engine, func, insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import Settings
from app.db.base import UnitOfWork
from app.db.schema.agent import AgentRun, UsageDaily
from app.db.schema.chat import Message, Thread
from app.db.schema.system import JobMarker
from app.db.schema.users import User

BACKEND = Path(__file__).parents[3]
# Defaults only: model_construct reads neither the environment nor .env.
SERVER = make_url(Settings.model_construct().DATABASE_URL.get_secret_value())

CATALOG = {
    "columns": """
        select table_name, column_name, data_type, udt_name, character_maximum_length,
            numeric_precision, numeric_scale, is_nullable, column_default, is_identity,
            identity_generation, is_generated, generation_expression
        from information_schema.columns where table_schema = 'public'
    """,
    "constraints": """
        select conrelid::regclass::text, conname, pg_get_constraintdef(oid)
        from pg_constraint where connamespace = 'public'::regnamespace
    """,
    "indexes": "select tablename, indexname, indexdef from pg_indexes where schemaname = 'public'",
    "extensions": "select extname, extversion from pg_extension",
}


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


def core_ddl() -> str:
    core = (BACKEND.parent / "tech.md").read_text(encoding="utf-8")
    schema = core.split("\n## 5. ", 1)[1].split("\n## 6. ", 1)[0]
    return "\n".join(re.findall(r"```sql\n(.*?)```", schema, re.DOTALL))


def catalog(url: str) -> dict[str, set[tuple[object, ...]]]:
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = {name: conn.execute(text(query)).all() for name, query in CATALOG.items()}
    engine.dispose()
    # procrastinate and Alembic own their tables; §5 describes the rest.
    return {
        name: {
            tuple(row)
            for row in found
            if not str(row[0]).startswith(("procrastinate_", "alembic_"))
        }
        for name, found in rows.items()
    }


@pytest.fixture(scope="module")
def database_url() -> Iterator[str]:
    with scratch_database() as url:
        command.upgrade(alembic_config(url), "head")
        yield url


@pytest.fixture
def db(database_url: str) -> Iterator[Connection]:
    engine = create_engine(database_url)
    with engine.connect() as conn:
        yield conn  # never committed: closing rolls the test's rows back
    engine.dispose()


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()


def test_migrations_upgrade_match_models_and_downgrade() -> None:
    with scratch_database() as url:
        config = alembic_config(url)
        command.upgrade(config, "head")
        command.check(config)  # raises when the models and the migrations differ
        # Down to base passes through -1, back up to head passes through the last revision.
        command.downgrade(config, "base")
        command.upgrade(config, "head")


def test_schema_matches_core_ddl(database_url: str) -> None:
    with scratch_database() as ddl_url:
        engine = create_engine(ddl_url)
        with engine.begin() as conn:
            # The driver cursor runs the whole script: several statements, no parameters.
            conn.connection.cursor().execute(core_ddl())
        engine.dispose()
        expected = catalog(ddl_url)

    migrated = catalog(database_url)
    for name in CATALOG:
        assert migrated[name] == expected[name], name


def violated(db: Connection, statement: Executable) -> str | None:
    """Runs the statement in a savepoint and returns the constraint it breaks."""
    with pytest.raises(IntegrityError) as error, db.begin_nested():
        db.execute(statement)
    assert isinstance(error.value.orig, psycopg.Error)
    return error.value.orig.diag.constraint_name


def new_user(db: Connection) -> uuid.UUID:
    email = f"{uuid.uuid4().hex}@example.test"
    return db.execute(
        insert(User).values(email=email, password_hash="x").returning(User.id)
    ).scalar_one()


def first_run(db: Connection, user_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Thread and user message for a run: the keys of an agent_runs row."""
    thread_id = db.execute(insert(Thread).values(user_id=user_id).returning(Thread.id)).scalar_one()
    message = insert(Message).values(
        thread_id=thread_id, user_id=user_id, role="user", content="Что в портфеле?"
    )
    message_id = db.execute(message.returning(Message.id)).scalar_one()
    return {"thread_id": thread_id, "user_id": user_id, "user_message_id": message_id}


def test_second_active_run_of_a_user_is_rejected(db: Connection) -> None:
    run = first_run(db, new_user(db))
    db.execute(insert(AgentRun).values(**run))  # queued by default

    second = insert(AgentRun).values(**run, status="running")
    assert violated(db, second) == "agent_runs_one_active_idx"


def test_finished_runs_and_other_users_do_not_block_a_run(db: Connection) -> None:
    run = first_run(db, new_user(db))
    for status in ("done", "partial", "cancelled", "failed", "interrupted"):
        db.execute(insert(AgentRun).values(**run, status=status))
    db.execute(insert(AgentRun).values(**run))
    db.execute(insert(AgentRun).values(**first_run(db, new_user(db)), status="running"))

    active = select(func.count()).where(AgentRun.status.in_(["queued", "running"]))
    assert db.execute(active).scalar_one() == 2


def add_usage(db: Connection, user_id: uuid.UUID | None, amount: int) -> None:
    row = pg_insert(UsageDaily).values(
        day=date(2026, 9, 29), user_id=user_id, resource="llm:lite", amount=amount, calls=1
    )
    db.execute(
        row.on_conflict_do_update(
            index_elements=["day", "user_id", "resource"],
            set_={
                "amount": UsageDaily.amount + row.excluded.amount,
                "calls": UsageDaily.calls + row.excluded.calls,
            },
        )
    )


def test_usage_upsert_keeps_one_row_per_key_with_null_user(db: Connection) -> None:
    user_id = new_user(db)
    for amount in (100, 250):
        add_usage(db, None, amount)  # the whole service
        add_usage(db, user_id, amount)

    rows = db.execute(select(UsageDaily.user_id, UsageDaily.amount, UsageDaily.calls)).all()
    assert sorted(rows, key=str) == sorted([(None, 350, 2), (user_id, 350, 2)], key=str)


@pytest.mark.parametrize(
    ("values", "constraint"),
    [
        ({"email": "Owner@example.test"}, "users_email_check"),
        ({"role": "admin"}, "users_role_check"),
    ],
)
def test_user_checks(db: Connection, values: dict[str, str], constraint: str) -> None:
    user = {"email": "owner@example.test", "password_hash": "x"} | values
    assert violated(db, insert(User).values(**user)) == constraint


def test_email_is_unique(db: Connection) -> None:
    db.execute(insert(User).values(email="owner@example.test", password_hash="x"))

    again = insert(User).values(email="owner@example.test", password_hash="y")
    assert violated(db, again) == "users_email_key"


async def test_unit_of_work_commits_and_loads_server_defaults(engine: AsyncEngine) -> None:
    marker = JobMarker(key=uuid.uuid4().hex, value="done")

    async with UnitOfWork(engine) as session:
        session.add(marker)

    assert marker.created_at is not None  # came back with the INSERT, no lazy load
    async with UnitOfWork(engine) as session:
        assert await session.get(JobMarker, marker.key) is not None


async def test_unit_of_work_rolls_back_on_error(engine: AsyncEngine) -> None:
    key = uuid.uuid4().hex

    with pytest.raises(RuntimeError):
        async with UnitOfWork(engine) as session:
            session.add(JobMarker(key=key, value="lost"))
            await session.flush()
            raise RuntimeError("boom")

    async with UnitOfWork(engine) as session:
        assert await session.get(JobMarker, key) is None
