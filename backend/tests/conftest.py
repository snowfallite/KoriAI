import asyncio
import os
from collections.abc import Callable, Mapping
from pathlib import Path

import hypothesis
import pytest

from app.config import Settings

pytest_plugins = ["tests.support.api", "tests.support.faults", "tests.support.seed"]

LAYERS = frozenset({"unit", "property", "contract", "integration", "agent", "golden"})
TESTS_DIR = Path(__file__).parent

# CI runs HYPOTHESIS_PROFILE=ci (tech.md §14.3).
hypothesis.settings.register_profile("ci", max_examples=200)
hypothesis.settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # The layer marker follows the directory: tests/<layer>/<domain>/test_*.py.
    for item in items:
        layer = item.path.relative_to(TESTS_DIR).parts[0]
        if layer in LAYERS:
            item.add_marker(layer)


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    # psycopg's async mode cannot run on the Windows Proactor loop.
    return {"selector": asyncio.SelectorEventLoop}


@pytest.fixture(autouse=True)
def _hermetic_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # Tests see defaults and explicit overrides, never the shell's configuration.
    for name in Settings.model_fields:
        monkeypatch.delenv(name, raising=False)
