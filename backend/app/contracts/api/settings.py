"""User settings DTOs (tech.md §6.3)."""

from typing import Literal

from app.contracts.common import Contract

type ModelMode = Literal["auto", "lite", "pro", "max", "ultra"]
type AnswerStyle = Literal["concise", "detailed"]


class SettingsOut(Contract):
    model_mode: ModelMode
    answer_style: AnswerStyle
    default_account: str | None  # account alias; null means all accounts


class SettingsPatchIn(Contract):
    # Every field is optional. An explicit null default_account means all accounts,
    # so tell it from a missing field by model_fields_set.
    model_mode: ModelMode | None = None
    answer_style: AnswerStyle | None = None
    default_account: str | None = None
