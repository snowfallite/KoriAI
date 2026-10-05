"""Small parts of the gateways: the file store (§8.7), retries of reads (§8.1), the TTL cache
(§8.2), the pace and robots.txt of the e-disclosure adapter (§8.5)."""

import hashlib
import time
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.config import Settings
from app.core.cache import TtlCache
from app.core.errors import PermanentGatewayError, TransientGatewayError
from app.gateways.disclosure.edisclosure import download_key
from app.gateways.disclosure.edisclosure.adapter import EDisclosure
from app.gateways.disclosure.edisclosure.parse import parse_robots
from app.gateways.files.local import LocalFiles
from app.gateways.retry import with_retries


async def chunks(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


async def test_a_file_goes_in_and_comes_out(tmp_path: Path) -> None:
    files = LocalFiles(tmp_path)
    key = "docs/issuer/document/Отчет 6 мес.pdf"

    stored = await files.put(key, chunks(b"%PDF-", b"1.4"))

    assert (stored.key, stored.size) == (key, 8)
    assert stored.sha256 == hashlib.sha256(b"%PDF-1.4").hexdigest()
    assert await files.exists(key)
    assert b"".join([part async for part in files.open(key)]) == b"%PDF-1.4"
    await files.delete(key)
    assert not await files.exists(key)
    await files.delete(key)  # deleting twice is fine


async def test_a_failed_write_leaves_neither_the_file_nor_a_part(tmp_path: Path) -> None:
    files = LocalFiles(tmp_path)

    async def broken() -> AsyncIterator[bytes]:
        yield b"half"
        raise OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        await files.put("media/ab/abc", broken())

    assert not await files.exists("media/ab/abc")
    assert list((tmp_path / "media" / "ab").iterdir()) == []


@pytest.mark.parametrize("key", ["../etc/passwd", "/etc/passwd", "docs\\..\\x", "", "a/../../b"])
def test_a_key_stays_inside_the_data_dir(tmp_path: Path, key: str) -> None:
    with pytest.raises(ValueError, match="bad file key"):
        LocalFiles(tmp_path).local_path(key)


def test_the_key_of_a_download_has_no_path_tricks() -> None:
    assert download_key(5, "MSFO_6m2026.pdf.zip") == "downloads/edisclosure/5/MSFO_6m2026.pdf.zip"
    assert download_key(5, "../../etc/passwd") == "downloads/edisclosure/5/_.._etc_passwd"
    assert download_key(5, "..") == "downloads/edisclosure/5/file"


async def test_a_read_gets_two_more_tries_then_gives_up() -> None:
    tries: list[int] = []

    async def flaky() -> str:
        tries.append(1)
        raise TransientGatewayError("tinvest_unavailable", retry_after_s=0)

    with pytest.raises(TransientGatewayError):
        await with_retries(flaky, base_s=0)

    assert len(tries) == 3


async def test_a_read_that_recovers_returns_its_answer() -> None:
    tries: list[int] = []

    async def recovers() -> str:
        tries.append(1)
        if len(tries) < 3:
            raise TransientGatewayError("web_unavailable", retry_after_s=0.01)
        return "ok"

    started = time.monotonic()
    assert await with_retries(recovers) == "ok"
    assert time.monotonic() - started >= 0.02  # the pauses of Retry-After, not of the exponent


async def test_a_permanent_error_is_not_retried() -> None:
    tries: list[int] = []

    async def refused() -> str:
        tries.append(1)
        raise PermanentGatewayError("token_invalid")

    with pytest.raises(PermanentGatewayError):
        await with_retries(refused, base_s=0)

    assert tries == [1]


async def test_the_cache_keeps_a_value_for_its_ttl() -> None:
    now = [100.0]
    cache: TtlCache[str] = TtlCache(30, clock=lambda: now[0])
    loads: list[str] = []

    async def load() -> str:
        loads.append("x")
        return f"value {len(loads)}"

    assert await cache.get_or_load("k", load) == "value 1"
    now[0] += 29
    assert await cache.get_or_load("k", load) == "value 1"
    now[0] += 2
    assert await cache.get_or_load("k", load) == "value 2"


def test_a_full_cache_starts_over() -> None:
    cache: TtlCache[int] = TtlCache(60, max_items=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)

    assert (cache.get("a"), cache.get("b"), cache.get("c")) == (None, None, 3)


def edisclosure(tmp_path: Path, rps: float) -> EDisclosure:
    settings = Settings.model_construct(
        EDISCLOSURE_BASE_URL="https://www.e-disclosure.ru", EDISCLOSURE_RPS=rps, DATA_DIR=tmp_path
    )
    return EDisclosure(settings, LocalFiles(tmp_path))


async def test_the_adapter_keeps_the_pace_of_the_config(tmp_path: Path) -> None:
    adapter = edisclosure(tmp_path, rps=20)  # a request every 50 ms

    started = time.monotonic()
    for _ in range(3):
        await adapter._pace("https://www.e-disclosure.ru/portal/company.aspx?id=1")

    assert time.monotonic() - started >= 0.095


async def test_the_adapter_keeps_to_robots_txt_but_for_the_search(tmp_path: Path) -> None:
    adapter = edisclosure(tmp_path, rps=1000)
    robots = (Path(__file__).parents[2] / "fixtures" / "edisclosure" / "robots.txt").read_text()
    adapter._robots, _ = parse_robots(robots)

    with pytest.raises(PermanentGatewayError) as refused:
        await adapter._pace("https://www.e-disclosure.ru/Company/Search?query=x")
    await adapter._pace("https://www.e-disclosure.ru/api/search/companies", robots=False)

    assert refused.value.code == "forbidden"
