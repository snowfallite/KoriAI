"""The logo proxy (S1-11 AC 5, tech.md §3.5, §6.4, §8.2): GET /api/media/logos/{logo_base} serves
the logo of a known instrument from the T-Invest CDN once, then from the media cache on disk."""

import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.contracts.common import ErrorOut
from app.contracts.faults import FaultRule
from app.db.base import UnitOfWork
from app.db.schema.broker import Instrument
from app.gateways.factory import Gateways
from app.gateways.fakes import Fake
from app.gateways.fetch.fake import PIXEL

# §8.2: the logo of <base>.png lives at <CDN>/<base>x{160|320|640}.png.
CDN = "https://invest-brands.cdn-tinkoff.ru"


async def add_instrument(app: FastAPI, logo_base: str | None) -> None:
    async with UnitOfWork(app.state.engine) as session:
        session.add(
            Instrument(
                uid=uuid.uuid4(),
                ticker=f"T{uuid.uuid4().hex[:6].upper()}",
                class_code="TQBR",
                name="Тестовая компания",
                instrument_type="share",
                currency="RUB",
                logo_base=logo_base,
            )
        )


def fetch_fake(app: FastAPI) -> Fake:
    gateways: Gateways = app.state.gateways
    assert isinstance(gateways.fetch, Fake)
    return gateways.fetch


def fetched(app: FastAPI) -> list[str]:
    return [call.args["url"] for call in fetch_fake(app).calls]


def cached_files(app: FastAPI) -> list[Path]:
    root: Path = app.state.settings.DATA_DIR / "media"
    return [path for path in root.rglob("*") if path.is_file()] if root.exists() else []


async def test_a_known_logo_comes_from_the_cdn_once_then_from_the_cache(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    await add_instrument(app, "sber")

    first = await user_api.get("/api/media/logos/sber")
    second = await user_api.get("/api/media/logos/sber")

    for reply in (first, second):
        assert reply.status_code == 200, reply.text
        assert reply.headers["content-type"] == "image/png"
        assert reply.content == PIXEL
        assert reply.headers["cache-control"].startswith("private")
    assert fetched(app) == [f"{CDN}/sberx160.png"]
    assert fetch_fake(app).calls[0].args["max_bytes"] == app.state.settings.MEDIA_MAX_BYTES
    # maintenance.cleanup drops the media cache under DATA_DIR/media (§10.2).
    assert len(cached_files(app)) == 1


@pytest.mark.parametrize("size", [160, 320, 640])
async def test_the_size_picks_the_cdn_variant(
    app: FastAPI, user_api: httpx.AsyncClient, size: int
) -> None:
    await add_instrument(app, "gazprom")

    reply = await user_api.get("/api/media/logos/gazprom", params={"size": size})

    assert reply.status_code == 200
    assert fetched(app) == [f"{CDN}/gazpromx{size}.png"]


@pytest.mark.parametrize("size", ["100", "1600", "big"])
async def test_a_size_outside_the_cdn_set_is_refused(
    app: FastAPI, user_api: httpx.AsyncClient, size: str
) -> None:
    await add_instrument(app, "sber")

    reply = await user_api.get("/api/media/logos/sber", params={"size": size})

    assert reply.status_code == 422
    assert ErrorOut.model_validate(reply.json()).code == "validation_error"
    assert fetched(app) == []


async def test_a_logo_of_no_known_instrument_is_not_found(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    await add_instrument(app, None)

    reply = await user_api.get("/api/media/logos/sber")

    assert reply.status_code == 404
    assert ErrorOut.model_validate(reply.json()).code == "not_found"
    assert fetched(app) == []


@pytest.mark.parametrize("base", ["..", ".sber", "sber%20x", "x" * 129, "%2e%2e%2fsecret"])
async def test_a_malformed_logo_name_is_not_found(
    app: FastAPI, user_api: httpx.AsyncClient, base: str
) -> None:
    reply = await user_api.get(f"/api/media/logos/{base}")

    assert reply.status_code == 404
    assert ErrorOut.model_validate(reply.json()).code == "not_found"
    assert fetched(app) == []


async def test_a_logo_the_cdn_lacks_is_not_found_and_not_cached(
    app: FastAPI, user_api: httpx.AsyncClient, faults: Any
) -> None:
    await add_instrument(app, "sber")
    faults(FaultRule(method="fetch_image", mode="error", error_code="not_found"))

    missing = await user_api.get("/api/media/logos/sber")
    found = await user_api.get("/api/media/logos/sber")

    assert missing.status_code == 404
    assert ErrorOut.model_validate(missing.json()).code == "not_found"
    assert found.status_code == 200
    assert len(fetched(app)) == 2


async def test_a_cdn_outage_answers_503(
    app: FastAPI, user_api: httpx.AsyncClient, faults: Any
) -> None:
    await add_instrument(app, "sber")
    faults(FaultRule(method="fetch_image", mode="timeout"))

    reply = await user_api.get("/api/media/logos/sber")

    assert reply.status_code == 503
    assert ErrorOut.model_validate(reply.json()).code == "web_unavailable"
    assert cached_files(app) == []


async def test_a_logo_needs_a_session(app: FastAPI, api: httpx.AsyncClient) -> None:
    await add_instrument(app, "sber")

    reply = await api.get("/api/media/logos/sber")

    assert reply.status_code == 401
    assert fetched(app) == []
