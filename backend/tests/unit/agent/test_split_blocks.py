"""split_blocks on the shared vectors of seed/blocks_cases.json (tech.md §9.9, §11); the SPA runs
the same cases in lib/utils/blocks.test.ts."""

import json
from typing import Any
from uuid import UUID

import pytest

from app.domains.agent.postprocess import split_blocks
from app.gateways.fixtures import SEED

VECTORS = json.loads((SEED / "blocks_cases.json").read_text(encoding="utf-8"))
CASES: list[dict[str, Any]] = VECTORS["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_split_blocks_follows_the_shared_vectors(case: dict[str, Any]) -> None:
    # The artifacts of the run in creation order: a dict keeps it.
    known = {artifact["local_id"]: UUID(artifact["id"]) for artifact in case["artifacts"]}

    found = split_blocks(case["text"], known)

    assert [block.model_dump(mode="json") for block in found.blocks] == case["blocks"]
    assert found.unknown == case["unknown"]
