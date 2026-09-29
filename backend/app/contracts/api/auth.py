"""Auth DTOs (tech.md §6.2)."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from app.contracts.api.broker import BrokerConnectionOut
from app.contracts.api.settings import SettingsOut
from app.contracts.common import Contract, UtcDatetime

PASSWORD_MIN_LENGTH = 10  # tech.md §3.5


class RegisterIn(Contract):
    email: str
    password: str = Field(min_length=PASSWORD_MIN_LENGTH)
    invite_code: str | None = None
    display_name: str | None = None


class LoginIn(Contract):
    email: str
    password: str


class PasswordChangeIn(Contract):
    current_password: str
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH)


class UserOut(Contract):
    id: UUID
    email: str
    display_name: str | None
    role: Literal["user", "owner"]
    created_at: UtcDatetime


class MeOut(Contract):
    user: UserOut
    settings: SettingsOut
    broker: BrokerConnectionOut
