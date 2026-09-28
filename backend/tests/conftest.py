from pathlib import Path

import pytest

LAYERS = frozenset({"unit", "property", "contract", "integration", "agent", "golden"})
TESTS_DIR = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # The layer marker follows the directory: tests/<layer>/<domain>/test_*.py.
    for item in items:
        layer = item.path.relative_to(TESTS_DIR).parts[0]
        if layer in LAYERS:
            item.add_marker(layer)
