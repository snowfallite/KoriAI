"""The tool steps of an answer in its meta (tech.md §6.6, v15)."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.contracts.api.chat import MessageMeta, ToolStepOut

STEP = {
    "tool": "portfolio_overview",
    "title": "Загружаю портфель",
    "ok": True,
    "error_code": None,
    "duration_ms": 412,
}


def test_a_meta_saved_before_v15_reads_without_steps() -> None:
    saved = {"model_family": "lite", "model_id": "GigaChat-2", "warnings": [], "disclaimer": False}

    assert MessageMeta.model_validate(saved).tools == []


def test_the_steps_keep_the_order_of_the_calls() -> None:
    failed = {**STEP, "tool": "calc", "title": "Считаю", "ok": False}
    failed["error_code"] = "validation_error"

    meta = MessageMeta.model_validate({"tools": [STEP, failed]})

    assert [step.tool for step in meta.tools] == ["portfolio_overview", "calc"]
    assert meta.tools[1].error_code == "validation_error"


@pytest.mark.parametrize(
    "broken",
    [
        {**STEP, "tool": "place_order"},
        {**STEP, "error_code": "timeout"},
        {**STEP, "summary": "Портфель загружен"},
        {key: value for key, value in STEP.items() if key != "duration_ms"},
    ],
)
def test_a_step_takes_only_the_tools_and_codes_of_the_contract(broken: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ToolStepOut.model_validate(broken)
