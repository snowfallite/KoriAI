"""Account commands of the CLI (S1-05; tech.md §15.4, §22.1): invite links and the owner."""

import asyncio
import getpass
import uuid
from pathlib import Path

import httpx
import pytest

from app import cli
from app.contracts.api.auth import UserOut


@pytest.fixture(autouse=True)
def _cli_database(database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The commands commit on their own connection; the app of the test still reads their rows.
    monkeypatch.chdir(tmp_path)  # away from a local .env
    monkeypatch.setenv("DATABASE_URL", database_url)


async def run(*argv: str) -> None:
    # The commands start their own event loop.
    await asyncio.to_thread(cli.main, list(argv))


async def test_an_invite_link_registers_a_user(
    api: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    await run("invites", "create", "--count", "2")

    links = capsys.readouterr().out.split()
    assert len(links) == 2
    prefix = "http://localhost:5173/register?invite="  # APP_BASE_URL
    assert all(link.startswith(prefix) for link in links)
    body = {"email": f"{uuid.uuid4().hex[:8]}@example.test", "password": "correct-horse-1"}
    reply = await api.post(
        "/api/auth/register", json={**body, "invite_code": links[0].removeprefix(prefix)}
    )
    assert reply.status_code == 201, reply.text


async def test_create_owner_makes_an_owner_and_resets_the_password(
    api: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    address = f"boss-{uuid.uuid4().hex[:8]}@example.test"
    for password in ("first-password-1", "second-password-2"):
        monkeypatch.setattr(getpass, "getpass", lambda _prompt="", typed=password: typed)
        await run("create-owner", "--email", address.upper())

    old = {"email": address, "password": "first-password-1"}
    assert (await api.post("/api/auth/login", json=old)).status_code == 401
    reply = await api.post("/api/auth/login", json={**old, "password": "second-password-2"})
    assert reply.status_code == 200, reply.text
    assert UserOut.model_validate(reply.json()).role == "owner"


async def test_create_owner_refuses_a_short_password(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(getpass, "getpass", lambda _prompt="": "x" * 9)

    with pytest.raises(SystemExit) as stop:
        await run("create-owner", "--email", "boss@example.test")

    assert stop.value.code == 1
    assert "10" in capsys.readouterr().err
