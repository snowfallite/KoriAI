"""instruments.service.resolve (tech.md §9.7): a ticker, TICKER_CLASSCODE, an ISIN, a uid or a name
gives one instrument, Ambiguous with candidates, or not_found. Runs on the T-Invest fake and the
test transaction; expectations come from seed/tinvest/instruments.yaml."""

import uuid
from typing import Any

import pytest
import yaml
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import select

from app.core.errors import AppError
from app.db.base import UnitOfWork
from app.db.schema.broker import Instrument
from app.domains.instruments.service import Ambiguous, InstrumentsService
from app.gateways.factory import Gateways
from app.gateways.fixtures import SEED

TOKEN = SecretStr("t.fake-read-only")


def seed_instrument(ticker: str) -> dict[str, Any]:
    items = yaml.safe_load((SEED / "tinvest" / "instruments.yaml").read_text(encoding="utf-8"))
    [item] = [item for item in items if item["ticker"] == ticker]
    found: dict[str, Any] = item
    return found


def service(app: FastAPI) -> InstrumentsService:
    gateways: Gateways = app.state.gateways
    return InstrumentsService(UnitOfWork(app.state.engine), gateways.tinvest)


@pytest.mark.parametrize(
    "text",
    [
        "SBER",
        " sber ",  # a ticker in any case, with stray spaces
        "SBER_TQBR",
        "RU0009029540",  # the ISIN
        "ab9bea9c-dda2-5b58-94a5-474347be4e9d",  # the instrument uid
    ],
)
async def test_one_instrument_comes_back_as_its_brief(app: FastAPI, text: str) -> None:
    sber = seed_instrument("SBER")

    found = await service(app).resolve(TOKEN, text)

    assert not isinstance(found, Ambiguous)
    assert (str(found.uid), found.ticker, found.class_code, found.name) == (
        sber["uid"],
        sber["ticker"],
        sber["class_code"],
        sber["name"],
    )
    assert found.logo_url == "/api/media/logos/sber"
    assert found.brand_color == sber["brand_color"]


async def test_a_ticker_with_underscores_resolves_too(app: FastAPI) -> None:
    found = await service(app).resolve(TOKEN, "EUR_RUB__TOM")

    assert not isinstance(found, Ambiguous)
    assert (found.ticker, found.class_code) == ("EUR_RUB__TOM", "CETS")


async def test_several_matches_come_back_as_candidates(app: FastAPI) -> None:
    found = await service(app).resolve(TOKEN, "ОФЗ")

    assert isinstance(found, Ambiguous)
    assert {c.ticker for c in found.candidates} == {"SU26238RMFS4", "SU29024RMFS5"}


async def test_nothing_found_is_not_found(app: FastAPI) -> None:
    with pytest.raises(AppError) as missing:
        await service(app).resolve(TOKEN, "нет такой бумаги")

    assert missing.value.code == "not_found"


async def test_an_unknown_uid_is_not_found(app: FastAPI) -> None:
    with pytest.raises(AppError) as missing:
        await service(app).resolve(TOKEN, str(uuid.uuid4()))

    assert missing.value.code == "not_found"


async def test_a_blank_query_is_refused(app: FastAPI) -> None:
    with pytest.raises(AppError) as refused:
        await service(app).resolve(TOKEN, "   ")

    assert refused.value.code == "validation_error"


async def test_a_resolved_instrument_is_stored(app: FastAPI) -> None:
    found = await service(app).resolve(TOKEN, "GAZP")

    assert not isinstance(found, Ambiguous)
    async with UnitOfWork(app.state.engine) as session:
        row = await session.scalar(select(Instrument).where(Instrument.uid == found.uid))
    assert row is not None
    assert (row.ticker, row.logo_base, row.lot) == (
        "GAZP",
        "gazprom",
        seed_instrument("GAZP")["lot"],
    )
