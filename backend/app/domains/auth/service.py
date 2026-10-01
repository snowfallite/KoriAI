"""Accounts, sessions and invites (tech.md §3.5, §6.2)."""

import asyncio
import re
from datetime import timedelta
from typing import Literal

from app.config import Settings
from app.contracts.api.auth import (
    PASSWORD_MIN_LENGTH,
    LoginIn,
    MeOut,
    PasswordChangeIn,
    RegisterIn,
    UserOut,
)
from app.core.errors import AppError
from app.core.security import (
    Principal,
    RateLimiter,
    hash_password,
    new_token,
    token_digest,
    verify_password,
)
from app.db.base import UnitOfWork
from app.domains.auth import repo
from app.domains.auth.repo import Ip
from app.domains.broker.service import BrokerService
from app.domains.settings.service import SettingsService

# Attempts a minute of each of login and registration (tech.md §3.5).
IP_LIMIT = 10
EMAIL_LIMIT = 5
INVITE_TTL = timedelta(days=14)
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
# An unknown email still costs one hash check: the answer time does not reveal accounts.
_NO_USER_HASH = hash_password(new_token())
_BAD_EMAIL = "Проверьте email"
_BAD_LOGIN = "Неверный email или пароль"


def normalize_email(raw: str) -> str | None:
    """Trimmed and lower-cased (§5.1); None for anything but one address."""
    email = raw.strip().lower()
    return email if len(email) <= 254 and _EMAIL.fullmatch(email) else None


def user_out(user: object) -> UserOut:
    return UserOut.model_validate(user, from_attributes=True)


class AuthService:
    def __init__(self, uow: UnitOfWork, settings: Settings, limiter: RateLimiter) -> None:
        self._uow = uow
        self._settings = settings
        self._limiter = limiter
        self._ttl = timedelta(days=settings.SESSION_TTL_DAYS)

    def _limit(self, action: Literal["login", "register"], ip: Ip, email: str) -> None:
        if not (
            self._limiter.hit(f"{action}:ip:{ip}", IP_LIMIT)
            and self._limiter.hit(f"{action}:email:{email}", EMAIL_LIMIT)
        ):
            raise AppError("rate_limited", "Слишком много попыток, повторите через минуту")

    async def register(
        self, body: RegisterIn, ip: Ip, user_agent: str | None
    ) -> tuple[UserOut, str]:
        """The new user and the token of their first session."""
        email = normalize_email(body.email)
        self._limit("register", ip, email or body.email[:254])
        mode = self._settings.REGISTRATION_MODE
        if mode == "closed":
            raise AppError("registration_closed", "Регистрация закрыта")
        code = (body.invite_code or "").strip()
        if mode == "invite" and not code:
            raise AppError("invite_required", "Нужен код приглашения")
        if email is None:
            raise AppError("validation_error", _BAD_EMAIL)
        password_hash = await asyncio.to_thread(hash_password, body.password)
        token = new_token()
        async with self._uow as session:
            # The invite goes first: without a live code the answer says nothing about the email.
            invite_id = None
            if mode == "invite":
                invite_id = await repo.claim_invite(session, token_digest(code))
                if invite_id is None:
                    raise AppError("invite_invalid", "Код приглашения недействителен")
            name = (body.display_name or "").strip() or None
            user = await repo.add_user(session, email, password_hash, name)
            if user is None:
                raise AppError("email_taken", "Этот email уже зарегистрирован")
            if invite_id is not None:
                await repo.bind_invite(session, invite_id, user.id)
            await repo.add_session(session, user.id, token_digest(token), self._ttl, ip, user_agent)
            await repo.add_audit(session, "register", user.id, ip)
        return user_out(user), token

    async def login(self, body: LoginIn, ip: Ip, user_agent: str | None) -> tuple[UserOut, str]:
        """The user and the token of a new session."""
        email = normalize_email(body.email)
        self._limit("login", ip, email or body.email[:254])
        async with self._uow as session:
            user = await repo.user_by_email(session, email) if email else None
        active = user if user is not None and user.status == "active" else None
        password_hash = active.password_hash if active else _NO_USER_HASH
        valid = await asyncio.to_thread(verify_password, password_hash, body.password)
        if active is None or not valid:
            async with self._uow as session:
                await repo.add_audit(session, "login_failed", user.id if user else None, ip)
            raise AppError("invalid_credentials", _BAD_LOGIN)
        token = new_token()
        async with self._uow as session:
            await repo.add_session(
                session, active.id, token_digest(token), self._ttl, ip, user_agent
            )
            await repo.set_last_login(session, active.id)
            await repo.add_audit(session, "login", active.id, ip)
        return user_out(active), token

    async def authenticate(self, token: str) -> Principal | None:
        """The user of a live session, whose expiry slides forward (§3.5)."""
        async with self._uow as session:
            found = await repo.touch_session(session, token_digest(token), self._ttl)
        if found is None:
            return None
        session_id, user_id, role = found
        return Principal(user_id=user_id, session_id=session_id, role=role)

    async def me(self, principal: Principal) -> MeOut:
        async with self._uow as session:
            user = await repo.user(session, principal.user_id)
        if user is None:  # deleted after the session check
            raise AppError("unauthorized", "Войдите в аккаунт")
        return MeOut(
            user=user_out(user),
            settings=await SettingsService(self._uow).get(principal.user_id),
            broker=await BrokerService(self._uow).connection(principal.user_id),
        )

    async def logout(self, principal: Principal, ip: Ip) -> None:
        async with self._uow as session:
            await repo.delete_sessions(session, principal.user_id, only=principal.session_id)
            await repo.add_audit(session, "logout", principal.user_id, ip)

    async def logout_all(self, principal: Principal, ip: Ip) -> None:
        async with self._uow as session:
            await repo.delete_sessions(session, principal.user_id)
            await repo.add_audit(session, "logout_all", principal.user_id, ip)

    async def change_password(self, principal: Principal, body: PasswordChangeIn, ip: Ip) -> None:
        """Ends every other session of the user (§6.2)."""
        async with self._uow as session:
            user = await repo.user(session, principal.user_id)
        current = user.password_hash if user else _NO_USER_HASH
        if not await asyncio.to_thread(verify_password, current, body.current_password):
            raise AppError("invalid_credentials", "Неверный текущий пароль")
        password_hash = await asyncio.to_thread(hash_password, body.new_password)
        async with self._uow as session:
            await repo.set_password(session, principal.user_id, password_hash)
            await repo.delete_sessions(session, principal.user_id, keep=principal.session_id)
            await repo.add_audit(session, "password_changed", principal.user_id, ip)

    async def create_invites(self, count: int) -> list[str]:
        """Codes for the registration links; only their hashes stay in the database."""
        codes = [new_token(12) for _ in range(count)]
        async with self._uow as session:
            await repo.add_invites(session, [token_digest(code) for code in codes], INVITE_TTL)
        return codes

    async def create_owner(self, email: str, password: str) -> None:
        """Creates the owner, or makes an existing user the owner with this password."""
        normalized = normalize_email(email)
        if normalized is None:
            raise AppError("validation_error", _BAD_EMAIL)
        if len(password) < PASSWORD_MIN_LENGTH:
            raise AppError("validation_error", f"Пароль не короче {PASSWORD_MIN_LENGTH} символов")
        password_hash = await asyncio.to_thread(hash_password, password)
        async with self._uow as session:
            await repo.upsert_owner(session, normalized, password_hash)
