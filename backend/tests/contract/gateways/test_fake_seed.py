"""With every *_MODE=fake the clients of the app answer from the seed (S1-09 AC 1, tech.md §8.1,
§15.2). Expectations come from the fixture files read here, not through the fakes."""

import csv
import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import yaml
from fastapi import FastAPI
from langchain_core.messages import HumanMessage
from pydantic import SecretStr

from app.contracts.llm import LlmCallCtx
from app.contracts.tinvest import TOperationsQuery
from app.contracts.vectors import ChunkPayload, ChunkPoint, ChunkQuery
from app.contracts.web import WebExtractQuery, WebSearchQuery
from app.gateways.factory import Gateways
from app.gateways.fakes import Fake
from app.gateways.fixtures import SEED

TOKEN = SecretStr("t.fake-read-only")
ALL_TIME = (datetime(2000, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC))


def seed_yaml(*parts: str) -> Any:
    return yaml.safe_load(SEED.joinpath(*parts).read_text(encoding="utf-8"))


def seed_csv(*parts: str) -> list[dict[str, str]]:
    with SEED.joinpath(*parts).open(encoding="utf-8", newline="") as rows:
        return list(csv.DictReader(rows))


def gateways(app: FastAPI) -> Gateways:
    found: Gateways = app.state.gateways
    return found


def uid_of(ticker: str) -> UUID:
    [found] = [i["uid"] for i in seed_yaml("tinvest", "instruments.yaml") if i["ticker"] == ticker]
    return UUID(found)


async def test_every_client_of_the_app_is_a_fake(app: FastAPI) -> None:
    g = gateways(app)
    ports = [g.tinvest, g.llm, g.web.inner, g.disclosure, g.embeddings, g.vectors, g.fetch]  # type: ignore[attr-defined]

    assert all(isinstance(port, Fake) for port in ports)


async def test_tinvest_gives_the_seed_accounts_and_portfolios(app: FastAPI) -> None:
    tinvest = gateways(app).tinvest
    accounts = seed_yaml("tinvest", "accounts.yaml")

    assert [a.id for a in await tinvest.get_accounts(TOKEN)] == [a["id"] for a in accounts]
    for account in accounts:
        portfolio = await tinvest.get_portfolio(TOKEN, account["id"])
        expected = seed_yaml("tinvest", "portfolios", f"{account['id']}.yaml")
        assert portfolio.total.amount == Decimal(expected["total"]["amount"])
        assert [str(p.instrument_uid) for p in portfolio.positions] == [
            p["instrument_uid"] for p in expected["positions"]
        ]


async def test_tinvest_pages_every_seed_operation_once(app: FastAPI) -> None:
    tinvest, account = gateways(app).tinvest, "2000000001"
    expected = {op["id"] for op in seed_yaml("tinvest", "operations", f"{account}.yaml")}

    seen: list[str] = []
    cursor = None
    while True:
        query = TOperationsQuery(
            account_id=account,
            from_=ALL_TIME[0],
            to=ALL_TIME[1],
            kinds=None,
            cursor=cursor,
            limit=7,
        )
        page = await tinvest.get_operations(TOKEN, query)
        seen += [op.id for op in page.items]
        if page.next_cursor is None:
            break
        cursor = page.next_cursor

    assert sorted(seen) == sorted(expected)


async def test_tinvest_finds_instruments_and_gives_their_candles(app: FastAPI) -> None:
    tinvest = gateways(app).tinvest
    sber, rows = uid_of("SBER"), seed_csv("tinvest", "candles", "SBER.csv")

    found = await tinvest.find_instruments(TOKEN, "сбер")
    candles = await tinvest.get_candles(TOKEN, sber, *ALL_TIME, "day")
    [last] = await tinvest.get_last_prices(TOKEN, [sber])

    assert found[0].ticker == "SBER"
    assert (await tinvest.get_instrument(TOKEN, sber)).isin == "RU0009029540"
    assert [c.close for c in candles] == [Decimal(row["close"]) for row in rows]
    assert last.price == Decimal(rows[-1]["close"])


async def test_tinvest_gives_the_reference_data_of_an_instrument(app: FastAPI) -> None:
    tinvest, sber = gateways(app).tinvest, uid_of("SBER")
    asset = next(
        i["asset_uid"] for i in seed_yaml("tinvest", "instruments.yaml") if i["ticker"] == "SBER"
    )
    years = (date(2000, 1, 1), date(2100, 1, 1))

    [fundamentals] = await tinvest.get_fundamentals(TOKEN, [UUID(asset)])
    forecasts = await tinvest.get_forecasts(TOKEN, sber)
    dividends = await tinvest.get_dividends(TOKEN, sber, *years)
    reports = await tinvest.get_report_schedule(TOKEN, sber, *years)
    ofz = await tinvest.get_coupons(TOKEN, uid_of("SU26238RMFS4"), *years)

    assert fundamentals.pe_ttm == Decimal("4.3")
    assert forecasts.consensus is not None
    assert (
        forecasts.consensus.recommendation
        == seed_yaml("tinvest", "forecasts.yaml")["SBER"]["consensus"]["recommendation"]
    )
    assert [d.record_date for d in dividends] == [
        d["record_date"] for d in seed_yaml("tinvest", "dividends.yaml")["SBER"]
    ]
    assert len(reports) == 3  # SBER has three events in report_schedule.yaml
    assert len(ofz) == len(seed_yaml("tinvest", "coupons.yaml")["SU26238RMFS4"])


async def test_web_answers_the_seed_query_without_case_or_extra_spaces(app: FastAPI) -> None:
    web = gateways(app).web
    [entry] = seed_yaml("web", "sber.yaml")["search"]
    query = WebSearchQuery(
        query="  Сбербанк   НОВОСТИ ",
        topic="news",
        depth="basic",
        time_range=None,
        max_results=10,
        include_domains=[],
        exclude_domains=[],
        include_images=True,
    )

    found = await web.search(query)

    assert [hit.url for hit in found.hits] == [hit["url"] for hit in entry["hits"]]
    assert [image.url for image in found.images] == [image["url"] for image in entry["images"]]
    assert (found.credits, found.cached) == (1, False)


async def test_web_extract_fails_the_pages_it_has_no_fixture_for(app: FastAPI) -> None:
    web = gateways(app).web
    known = seed_yaml("web", "sber.yaml")["extract"][0]["url"]
    query = WebExtractQuery.model_validate(
        {"urls": [known, "https://nowhere.example.org/page"], "depth": "basic"}
    )

    found = await web.extract(query)

    assert [page.url for page in found.pages] == [known]
    assert [failure.url for failure in found.failed] == ["https://nowhere.example.org/page"]
    assert found.credits == 1


async def test_disclosure_gives_cards_files_and_archives(app: FastAPI, tmp_path: Path) -> None:
    disclosure = gateways(app).disclosure
    rows = seed_yaml("edisclosure", "files", "3043.yaml")
    [archive] = SEED.joinpath("edisclosure", "archives", "1941660").iterdir()

    card = await disclosure.get_company(3043)
    ras = await disclosure.list_files(3043, "ras")
    hits = await disclosure.search_companies("7707083893")
    downloaded = await disclosure.download(1941660)

    assert (card.inn, card.short_name) == ("7707083893", "ПАО Сбербанк")
    assert [r.file_id for r in ras] == [r["file_id"] for r in rows if r["section"] == "ras"]
    assert [hit.company_id for hit in hits] == [3043]
    assert downloaded.sha256 == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert downloaded.storage_key == f"downloads/edisclosure/1941660/{archive.name}"
    stored = gateways(app).files.local_path(downloaded.storage_key)
    assert stored.read_bytes() == archive.read_bytes()


async def test_the_model_plays_the_seed_scenario(app: FastAPI) -> None:
    g = gateways(app)
    [_, scenario] = seed_yaml("llm", "smalltalk.yaml")
    ctx = LlmCallCtx(
        purpose="agent_step", priority="interactive", family="lite", model_id="GigaChat-2"
    )

    answer = await g.metering.invoke(
        g.llm.chat_model("GigaChat-2", streaming=False), [HumanMessage("Привет!")], ctx=ctx
    )

    assert answer.text == scenario["steps"][0]["text"]
    assert answer.usage_metadata is not None
    assert answer.usage_metadata["input_tokens"] == scenario["usage"]["prompt_tokens"]


async def test_embeddings_vectors_and_fetch_answer_without_a_network(app: FastAPI) -> None:
    g = gateways(app)
    text = "Выручка Сбербанка за полугодие"
    payload = ChunkPayload(
        document_id=uuid4(),
        issuer_id=uuid4(),
        kind="ifrs_interim",
        standard="ifrs",
        period_year=2026,
        period_label="2026, 6 месяцев",
        page=3,
        chunk_idx=0,
        text=text,
    )
    [dense] = await g.embeddings.embed_passages([text])
    [sparse] = await g.embeddings.sparse_passages([text])
    await g.vectors.ensure_collection()
    await g.vectors.upsert([ChunkPoint(id=uuid4(), dense=dense, sparse=sparse, payload=payload)])

    hits = await g.vectors.search(
        ChunkQuery(
            text="выручка",
            dense=await g.embeddings.embed_query("выручка"),
            sparse=await g.embeddings.sparse_query("выручка"),
            issuer_id=payload.issuer_id,
            kinds=None,
            years=[2026],
            top_k=3,
        )
    )
    image = await g.fetch.fetch_image("https://news.example.com/logo.png", max_bytes=1024)

    assert len(dense) == g.embeddings.dense_dim() == 384
    assert [hit.payload for hit in hits] == [payload]
    assert image.content_type == "image/png"
    assert image.data.startswith(b"\x89PNG")
