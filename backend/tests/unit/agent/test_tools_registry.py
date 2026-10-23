"""The registry of the agent tools (tech.md §9.4, §9.7): a module tools/<name>.py exports SPEC
and async run, and only the tools found there reach the routing."""

import types
from typing import Any, get_args

import pytest

from app.contracts.agent import CalcArgs, ToolResult, ToolSpec
from app.contracts.common import ToolName
from app.domains.agent.tools import available, tool_of

SPEC = ToolSpec(
    name="calc",
    group="calc",
    title="Считаю",
    description="Считает выражение",
    args_model=CalcArgs,
    few_shot_examples=[],
    timeout_s=10,
)


async def run(args: Any, ctx: Any) -> ToolResult:
    return ToolResult(ok=True, summary="25")


def module(name: str, **exports: Any) -> types.ModuleType:
    found = types.ModuleType(f"app.domains.agent.tools.{name}")
    for key, value in exports.items():
        setattr(found, key, value)
    return found


def test_a_module_with_its_spec_and_run_is_a_tool() -> None:
    tool = tool_of(module("calc", SPEC=SPEC, run=run))

    assert (tool.spec, tool.run) == (SPEC, run)


@pytest.mark.parametrize(
    "broken",
    [
        module("calc", run=run),
        module("calc", SPEC=SPEC),
        module("calc", SPEC=SPEC, run=lambda args, ctx: None),
        module("calc", SPEC={"name": "calc"}, run=run),
        module("make_table", SPEC=SPEC, run=run),
    ],
)
def test_a_module_without_its_spec_or_run_breaks_the_start(broken: types.ModuleType) -> None:
    with pytest.raises(TypeError):
        tool_of(broken)


def test_the_tools_of_the_code_carry_names_of_the_contract() -> None:
    assert available() <= frozenset(get_args(ToolName.__value__))
