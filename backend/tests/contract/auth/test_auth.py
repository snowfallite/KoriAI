"""Auth contract (S1-05 AC 1-5; tech.md §3.5, §5.1, §6.1, §6.2): accounts, sessions, guards."""

import hashlib
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta
from http.cookies import Morsel, SimpleCookie

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.contracts.api.auth import MeOut, UserOut
from app.contracts.api.broker import BrokerConnectionOut
from app.contracts.api.settings import SettingsOut
from app.contracts.common import ErrorOut
from app.db.schema.broker import BrokerAccount, BrokerConnection
from app.db.schema.users import AuditEvent, Invite, User, UserSession, UserSettings

PASSWORD = "correct-horse-1"
NEW_PASSWORD = "battery-staple-2"
THIRTY_DAYS = str(30 * 24 * 3600)  # SESSION_TTL_DAYS
PUBLIC = {
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("GET", "/api/health"),
    ("GET", "/api/health/ready"),
}

type Invites = Callable[[], Awaitable[str]]


def email() -> str:
    return f"user-{uuid.uuid4().hex[:8]}@example.test"


def sha256(text: str) -> bytes:
    return hashlib.sha256(text.encode()).digest()


def db(app: FastAPI) -> AsyncConnection:
    conn: AsyncConnection = app.state.engine  # the test transaction (tests/support/api.py)
    return conn


def error(reply: httpx.Response, status: int) -> ErrorOut:
    assert reply.status_code == status, reply.text
    return ErrorOut.model_validate(reply.json())


def session_cookie(reply: httpx.Response) -> Morsel[str]:
    cookies: SimpleCookie = SimpleCookie()
    cookies.load(reply.headers["set-cookie"])
    return cookies["sid"]


async def register(
    api: httpx.AsyncClient,
    invite: str | None,
    address: str | None = None,
    password: str = PASSWORD,
    display_name: str | None = None,
) -> httpx.Response:
    body = {
        "email": address or email(),
        "password": password,
        "invite_code": invite,
        "display_name": display_name,
    }
    return await api.post("/api/auth/register", json=body)


async def login(api: httpx.AsyncClient, address: str, password: str = PASSWORD) -> httpx.Response:
    return await api.post("/api/auth/login", json={"email": address, "password": password})


async def signed_up(api: httpx.AsyncClient, make_invite: Invites) -> tuple[UserOut, str]:
    address = email()
    reply = await register(api, await make_invite(), address)
    assert reply.status_code == 201, reply.text
    return UserOut.model_validate(reply.json()), address


def use_settings(app: FastAPI, **changes: object) -> None:
    app.state.settings = app.state.settings.model_copy(update=changes)


# Registration


async def test_register_by_invite_signs_in(api: httpx.AsyncClient, make_invite: Invites) -> None:
    reply = await register(api, await make_invite(), "  New.User@Example.TEST ", display_name="Аня")

    assert reply.status_code == 201, reply.text
    user = UserOut.model_validate(reply.json())
    assert (user.email, user.display_name, user.role) == ("new.user@example.test", "Аня", "user")
    cookie = session_cookie(reply)
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", cookie.value)  # 32 random bytes
    assert (cookie["path"], cookie["max-age"], cookie["samesite"]) == ("/", THIRTY_DAYS, "Lax")
    assert cookie["httponly"] is True
    assert not cookie["secure"]  # COOKIE_SECURE=false in dev and ci

    me = MeOut.model_validate((await api.get("/api/auth/me")).json())
    assert me.user == user
    assert me.settings == SettingsOut(
        model_mode="auto", answer_style="concise", default_account=None
    )
    assert me.broker == BrokerConnectionOut(
        connected=False, status=None, token_hint=None, last_verified_at=None, accounts=[]
    )


@pytest.mark.parametrize("code", [None, "", "   "])
async def test_invite_mode_without_a_code_is_invite_required(
    api: httpx.AsyncClient, code: str | None
) -> None:
    assert error(await register(api, code), 422).code == "invite_required"


async def test_an_unknown_used_or_expired_code_is_invite_invalid(
    app: FastAPI, api: httpx.AsyncClient, make_invite: Invites
) -> None:
    assert error(await register(api, "no-such-code"), 422).code == "invite_invalid"

    used = await make_invite()
    assert (await register(api, used)).status_code == 201
    assert error(await register(api, used), 422).code == "invite_invalid"

    expired = await make_invite()
    await db(app).execute(
        update(Invite)
        .where(Invite.code_hash == sha256(expired))
        .values(expires_at=func.now() - timedelta(seconds=1))
    )
    assert error(await register(api, expired), 422).code == "invite_invalid"


async def test_closed_registration_is_forbidden(
    app: FastAPI, api: httpx.AsyncClient, make_invite: Invites
) -> None:
    use_settings(app, REGISTRATION_MODE="closed")

    assert error(await register(api, await make_invite()), 403).code == "registration_closed"


async def test_open_registration_needs_no_code(app: FastAPI, api: httpx.AsyncClient) -> None:
    use_settings(app, REGISTRATION_MODE="open")

    assert (await register(api, None)).status_code == 201


async def test_a_taken_email_is_a_conflict_and_keeps_the_invite(
    api: httpx.AsyncClient, make_invite: Invites
) -> None:
    _, address = await signed_up(api, make_invite)
    spare = await make_invite()

    assert error(await register(api, spare, address.upper()), 409).code == "email_taken"
    assert (await register(api, spare)).status_code == 201


@pytest.mark.parametrize(
    "body",
    [{"email": "no-at-sign.example.test"}, {"email": "a b@example.test"}, {"password": "x" * 9}],
)
async def test_a_bad_email_or_a_short_password_is_a_validation_error(
    api: httpx.AsyncClient, make_invite: Invites, body: dict[str, str]
) -> None:
    full = {"email": email(), "password": PASSWORD, "invite_code": await make_invite(), **body}

    assert error(await api.post("/api/auth/register", json=full), 422).code == "validation_error"


async def test_the_database_keeps_hashes_not_secrets(
    app: FastAPI, api: httpx.AsyncClient, make_invite: Invites
) -> None:
    code = await make_invite()
    reply = await register(api, code)
    user = UserOut.model_validate(reply.json())

    conn = db(app)
    sessions = select(UserSession.token_hash).where(UserSession.user_id == user.id)
    assert await conn.scalar(sessions) == sha256(session_cookie(reply).value)
    assert await conn.scalar(select(Invite.used_by).where(Invite.code_hash == sha256(code))) == (
        user.id
    )
    password_hash = await conn.scalar(select(User.password_hash).where(User.id == user.id))
    assert password_hash is not None
    assert password_hash.startswith("$argon2id$")


# Sign-in and sessions


async def test_login_ignores_email_case_and_opens_another_session(
    api: httpx.AsyncClient, new_client: Callable[[], httpx.AsyncClient], make_invite: Invites
) -> None:
    user, address = await signed_up(api, make_invite)

    async with new_client() as phone:
        reply = await login(phone, f" {address.upper()} ")

        assert reply.status_code == 200, reply.text
        assert UserOut.model_validate(reply.json()) == user
        assert (await phone.get("/api/auth/me")).status_code == 200
    assert (await api.get("/api/auth/me")).status_code == 200


async def test_a_wrong_password_and_an_unknown_email_get_one_answer(
    api: httpx.AsyncClient, make_invite: Invites
) -> None:
    _, address = await signed_up(api, make_invite)

    wrong = error(await login(api, address, NEW_PASSWORD), 401)
    unknown = error(await login(api, email()), 401)

    assert wrong.code == unknown.code == "invalid_credentials"
    assert wrong.message == unknown.message


async def test_a_disabled_user_is_signed_out_and_cannot_sign_in(
    app: FastAPI, api: httpx.AsyncClient, make_invite: Invites
) -> None:
    user, address = await signed_up(api, make_invite)

    await db(app).execute(update(User).where(User.id == user.id).values(status="disabled"))

    assert error(await api.get("/api/auth/me"), 401).code == "unauthorized"
    assert error(await login(api, address), 401).code == "invalid_credentials"


async def test_each_request_slides_the_session(
    app: FastAPI, api: httpx.AsyncClient, make_invite: Invites
) -> None:
    user, _ = await signed_up(api, make_invite)
    mine = UserSession.user_id == user.id
    await db(app).execute(
        update(UserSession).where(mine).values(expires_at=func.now() + timedelta(hours=1))
    )

    reply = await api.get("/api/auth/me")

    assert reply.status_code == 200
    assert session_cookie(reply)["max-age"] == THIRTY_DAYS
    # now() stays put inside the test transaction.
    left = await db(app).scalar(select(UserSession.expires_at - func.now()).where(mine))
    assert left == timedelta(days=30)


async def test_an_expired_session_is_unauthorized(
    app: FastAPI, api: httpx.AsyncClient, make_invite: Invites
) -> None:
    user, _ = await signed_up(api, make_invite)

    await db(app).execute(
        update(UserSession)
        .where(UserSession.user_id == user.id)
        .values(expires_at=func.now() - timedelta(seconds=1))
    )

    assert error(await api.get("/api/auth/me"), 401).code == "unauthorized"


async def test_the_cookie_is_secure_when_configured(
    app: FastAPI, api: httpx.AsyncClient, make_invite: Invites
) -> None:
    use_settings(app, COOKIE_SECURE=True)

    assert session_cookie(await register(api, await make_invite()))["secure"] is True


async def test_logout_ends_this_session_only(
    api: httpx.AsyncClient, new_client: Callable[[], httpx.AsyncClient], make_invite: Invites
) -> None:
    _, address = await signed_up(api, make_invite)
    token = api.cookies["sid"]

    async with new_client() as phone:
        assert (await login(phone, address)).status_code == 200
        reply = await api.post("/api/auth/logout")

        assert reply.status_code == 204, reply.text
        assert (session_cookie(reply).value, session_cookie(reply)["max-age"]) == ("", "0")
        assert error(await api.get("/api/auth/me"), 401).code == "unauthorized"
        replay = await phone.get("/api/auth/me", headers={"Cookie": f"sid={token}"})
        assert error(replay, 401).code == "unauthorized"
        assert (await phone.get("/api/auth/me")).status_code == 200


async def test_logout_all_ends_every_session(
    api: httpx.AsyncClient, new_client: Callable[[], httpx.AsyncClient], make_invite: Invites
) -> None:
    _, address = await signed_up(api, make_invite)

    async with new_client() as phone:
        assert (await login(phone, address)).status_code == 200
        reply = await api.post("/api/auth/logout-all")

        assert reply.status_code == 204, reply.text
        assert session_cookie(reply)["max-age"] == "0"
        for client in (api, phone):
            assert error(await client.get("/api/auth/me"), 401).code == "unauthorized"


# Password


async def test_a_password_change_keeps_this_session_and_ends_the_others(
    api: httpx.AsyncClient, new_client: Callable[[], httpx.AsyncClient], make_invite: Invites
) -> None:
    _, address = await signed_up(api, make_invite)

    async with new_client() as phone:
        assert (await login(phone, address)).status_code == 200
        change = {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
        reply = await api.post("/api/auth/password", json=change)

        assert reply.status_code == 204, reply.text
        assert (await api.get("/api/auth/me")).status_code == 200
        assert error(await phone.get("/api/auth/me"), 401).code == "unauthorized"
        assert error(await login(phone, address), 401).code == "invalid_credentials"
        assert (await login(phone, address, NEW_PASSWORD)).status_code == 200


async def test_a_wrong_current_password_changes_nothing(
    api: httpx.AsyncClient, new_client: Callable[[], httpx.AsyncClient], make_invite: Invites
) -> None:
    _, address = await signed_up(api, make_invite)

    change = {"current_password": NEW_PASSWORD, "new_password": NEW_PASSWORD}
    reply = await api.post("/api/auth/password", json=change)

    assert error(reply, 401).code == "invalid_credentials"
    assert (await api.get("/api/auth/me")).status_code == 200
    async with new_client() as phone:
        assert (await login(phone, address)).status_code == 200


async def test_a_short_new_password_is_a_validation_error(
    api: httpx.AsyncClient, make_invite: Invites
) -> None:
    await signed_up(api, make_invite)

    change = {"current_password": PASSWORD, "new_password": "x" * 9}
    reply = await api.post("/api/auth/password", json=change)

    assert error(reply, 422).code == "validation_error"


# Me


async def test_me_shows_saved_settings_and_the_broker(
    app: FastAPI, api: httpx.AsyncClient, make_invite: Invites
) -> None:
    user, _ = await signed_up(api, make_invite)
    conn = db(app)
    await conn.execute(
        insert(UserSettings).values(
            user_id=user.id, model_mode="pro", answer_style="detailed", default_account="acc2"
        )
    )
    connection_id = await conn.scalar(
        insert(BrokerConnection)
        .values(
            user_id=user.id,
            token_ciphertext=b"sealed",
            token_nonce=bytes(12),
            token_key_id="k1",
            token_hint="ab12",
        )
        .returning(BrokerConnection.id)
    )
    for alias in ("acc10", "acc2", "acc1"):
        account = {"external_id": f"2000{alias}", "alias": alias, "name": f"Счёт {alias}"}
        await conn.execute(
            insert(BrokerAccount).values(
                connection_id=connection_id,
                type="broker",
                status="open",
                access_level="read_only",
                **account,
            )
        )

    me = MeOut.model_validate((await api.get("/api/auth/me")).json())

    assert me.settings == SettingsOut(
        model_mode="pro", answer_style="detailed", default_account="acc2"
    )
    assert (me.broker.connected, me.broker.status, me.broker.token_hint) == (True, "active", "ab12")
    assert [account.alias for account in me.broker.accounts] == ["acc1", "acc2", "acc10"]


# Guards


async def test_every_route_but_the_public_ones_needs_a_session(
    app: FastAPI, api: httpx.AsyncClient
) -> None:
    # The schema lists every route of the API, whatever slice added it.
    routes = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    assert routes >= PUBLIC | {("GET", "/api/auth/me"), ("POST", "/api/auth/logout")}

    for method, path in sorted(routes - PUBLIC):
        url = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)
        reply = await api.request(method, url)
        assert error(reply, 401).code == "unauthorized", (method, path)
    assert error(await api.get("/api/no-such-route"), 401).code == "unauthorized"


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": None},
        {"Content-Type": "text/plain"},
        {"Content-Type": "application/x-www-form-urlencoded"},
        {"Content-Type": None},
    ],
)
async def test_a_mutation_needs_our_origin_and_json(
    api: httpx.AsyncClient, make_invite: Invites, headers: dict[str, str | None]
) -> None:
    _, address = await signed_up(api, make_invite)

    for path, body in [
        ("/api/auth/login", {"email": address, "password": PASSWORD}),
        ("/api/auth/logout", None),
    ]:
        request = api.build_request("POST", path, json=body)
        for name, value in headers.items():
            if value is None:
                del request.headers[name]
            else:
                request.headers[name] = value
        assert error(await api.send(request), 403).code == "forbidden", path

    # The refused logout did not end the session; reads take any origin.
    me = await api.get("/api/auth/me", headers={"Origin": "https://evil.example"})
    assert me.status_code == 200


@pytest.mark.parametrize(
    ("path", "code"),
    [("/api/auth/login", "invalid_credentials"), ("/api/auth/register", "invite_required")],
)
async def test_the_eleventh_attempt_a_minute_from_one_ip_is_rate_limited(
    api: httpx.AsyncClient, path: str, code: str
) -> None:
    attempt = {"password": PASSWORD}
    for _ in range(10):
        reply = await api.post(path, json={**attempt, "email": email()})
        assert reply.status_code in {401, 422}
        assert ErrorOut.model_validate(reply.json()).code == code

    limited = await api.post(path, json={**attempt, "email": email()})
    assert error(limited, 429).code == "rate_limited"


async def test_the_sixth_attempt_a_minute_on_one_email_is_rate_limited(
    api: httpx.AsyncClient, make_invite: Invites
) -> None:
    _, address = await signed_up(api, make_invite)

    for _ in range(5):
        assert error(await login(api, address, NEW_PASSWORD), 401).code == "invalid_credentials"
    # Even the right password waits out the minute.
    assert error(await login(api, address), 429).code == "rate_limited"


async def test_the_audit_keeps_the_account_events(
    app: FastAPI, api: httpx.AsyncClient, make_invite: Invites
) -> None:
    user, address = await signed_up(api, make_invite)
    await login(api, address, NEW_PASSWORD)
    await login(api, address)
    await api.post(
        "/api/auth/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    )
    await api.post("/api/auth/logout")
    await login(api, address, NEW_PASSWORD)
    await api.post("/api/auth/logout-all")

    rows = await db(app).execute(
        select(AuditEvent.kind, AuditEvent.ip, AuditEvent.meta)
        .where(AuditEvent.user_id == user.id)
        .order_by(AuditEvent.id)
    )
    events = [(kind, str(ip), meta) for kind, ip, meta in rows]
    kinds = ["register", "login_failed", "login", "password_changed", "logout", "login"]
    assert events == [(kind, "127.0.0.1", {}) for kind in [*kinds, "logout_all"]]
