"""Invariants of split_blocks (tech.md §9.9, §11): no block holds a placeholder line, every
artifact of the run shows exactly once, placed ones in the order of the text and the rest after
them in creation order, and any text splits without an error."""

import re
import uuid
from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st

from app.contracts.api.chat import ArtifactBlock, MarkdownBlock
from app.domains.agent.postprocess import split_blocks

PLACEHOLDER = re.compile(r"^\s*\[\[([cti][0-9]+)\]\]\s*$")
POOL = ["c1", "c2", "c10", "t1", "t2", "i1"]
UNKNOWN = ["c9", "t7", "i4"]
ID = {local_id: uuid.uuid5(uuid.NAMESPACE_URL, local_id) for local_id in POOL}

placeholder_lines = st.builds(
    lambda pad, local_id, tail: f"{pad}[[{local_id}]]{tail}",
    st.sampled_from(["", " ", "  ", "\t"]),
    st.sampled_from(POOL + UNKNOWN),
    st.sampled_from(["", " ", "\t"]),
)
text_lines = st.text(alphabet=st.characters(blacklist_categories=["Cs"]), max_size=40)
texts = st.lists(st.one_of(placeholder_lines, text_lines), max_size=12).map("\n".join)
# The artifacts of a run in creation order.
runs = st.lists(st.sampled_from(POOL), unique=True).map(
    lambda ids: {local_id: ID[local_id] for local_id in ids}
)


def placed(text: str) -> list[str]:
    """Placeholder ids of the text in order of their first line."""
    found = [m.group(1) for line in text.split("\n") if (m := PLACEHOLDER.match(line))]
    return list(dict.fromkeys(found))


@given(texts, runs)
def test_no_block_holds_a_placeholder_line(text: str, known: dict[str, UUID]) -> None:
    for block in split_blocks(text, known).blocks:
        if isinstance(block, MarkdownBlock):
            assert block.text == block.text.strip() != ""
            assert not any(PLACEHOLDER.match(line) for line in block.text.split("\n"))


@given(texts, runs)
def test_every_artifact_shows_once_placed_first_then_in_creation_order(
    text: str, known: dict[str, UUID]
) -> None:
    shown = [
        b.artifact_id for b in split_blocks(text, known).blocks if isinstance(b, ArtifactBlock)
    ]

    in_text = [local_id for local_id in placed(text) if local_id in known]
    rest = [local_id for local_id in known if local_id not in in_text]
    assert shown == [known[local_id] for local_id in in_text + rest]


@given(texts, runs)
def test_unknown_lists_each_missing_placeholder_once(text: str, known: dict[str, UUID]) -> None:
    found = split_blocks(text, known)

    assert found.unknown == [local_id for local_id in placed(text) if local_id not in known]


@given(st.text(), runs)
def test_any_text_splits(text: str, known: dict[str, UUID]) -> None:
    split_blocks(text, known)
