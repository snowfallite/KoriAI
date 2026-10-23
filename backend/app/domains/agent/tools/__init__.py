"""The registry of the agent tools (tech.md §9.4, §9.7): every module tools/<name>.py exports
SPEC and async run. A slice adds its tool as a module and never edits this file (§16.1); the
routing keeps only the tools found here."""

import functools
import importlib
import inspect
import pkgutil
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from app.contracts.agent import ToolResult, ToolSpec
from app.contracts.common import ToolName


@dataclass(frozen=True, slots=True)
class Tool:
    spec: ToolSpec
    run: Callable[..., Awaitable[ToolResult]]  # run(args, ctx: ToolContext), F-07


def tool_of(module: ModuleType) -> Tool:
    """The tool of a module; a broken one stops the start of the process."""
    spec: Any = getattr(module, "SPEC", None)
    run: Any = getattr(module, "run", None)
    name = module.__name__.rsplit(".", 1)[-1]
    if not isinstance(spec, ToolSpec) or not inspect.iscoroutinefunction(run):
        raise TypeError(f"tool {name}: expected SPEC: ToolSpec and async def run")
    if spec.name != name:
        raise TypeError(f"tool {name}: SPEC names {spec.name}")
    return Tool(spec, run)


@functools.cache
def registry() -> Mapping[ToolName, Tool]:
    found = (
        tool_of(importlib.import_module(f"{__name__}.{module.name}"))
        for module in pkgutil.iter_modules(__path__)
    )
    return {tool.spec.name: tool for tool in found}


def available() -> frozenset[ToolName]:
    return frozenset(registry())
