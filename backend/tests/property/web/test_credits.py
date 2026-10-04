"""Tavily credits (tech.md §8.4): the estimate covers any answer, the formula holds its prices."""

import math

from hypothesis import given
from hypothesis import strategies as st

from app.contracts.web import WebCrawlQuery, WebExtractQuery, WebMapQuery
from app.gateways.web.credits import (
    crawl_credits,
    estimate,
    extract_credits,
    map_credits,
    search_credits,
)

depths = st.sampled_from(["basic", "advanced"])
instructions = st.one_of(st.none(), st.just("только новости"))


@given(st.integers(1, 20), depths, st.data())
def test_an_extract_never_costs_more_than_its_estimate(
    urls: int, depth: str, data: st.DataObject
) -> None:
    query = WebExtractQuery.model_validate(
        {"urls": [f"https://example.com/{n}" for n in range(urls)], "depth": depth}
    )
    extracted = data.draw(st.integers(0, urls))

    assert extract_credits(extracted, query.depth) <= estimate(query)


@given(st.integers(1, 10), instructions, st.data())
def test_a_crawl_never_costs_more_than_its_estimate(
    limit: int, text: str | None, data: st.DataObject
) -> None:
    query = WebCrawlQuery.model_validate(
        {"url": "https://example.com", "instructions": text, "max_depth": 1, "limit": limit,
         "select_paths": []}
    )  # fmt: skip
    pages = data.draw(st.integers(0, limit))

    assert crawl_credits(pages, text) <= estimate(query)


@given(st.integers(1, 50), instructions, st.data())
def test_a_map_never_costs_more_than_its_estimate(
    limit: int, text: str | None, data: st.DataObject
) -> None:
    query = WebMapQuery.model_validate(
        {"url": "https://example.com", "instructions": text, "max_depth": 1, "limit": limit}
    )
    urls = data.draw(st.integers(0, limit))

    assert map_credits(urls, text) <= estimate(query)


@given(st.integers(0, 200))
def test_the_price_list(pages: int) -> None:
    assert (search_credits("basic"), search_credits("advanced")) == (1, 2)
    assert extract_credits(pages, "basic") == math.ceil(pages / 5)
    assert extract_credits(pages, "advanced") == 2 * math.ceil(pages / 5)
    assert map_credits(pages, None) == math.ceil(pages / 10)
    assert map_credits(pages, "с инструкцией") == 2 * math.ceil(pages / 10)
    assert crawl_credits(pages, None) == map_credits(pages, None) + extract_credits(pages, "basic")
