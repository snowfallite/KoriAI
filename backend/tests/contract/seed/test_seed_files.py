"""Seed fixtures (S1-10, tech.md §15.2): every file validates against its contract model, no
file goes unchecked, and the files agree with each other, since the seed, the fakes and the
tests read the same data."""

# ruff: noqa: RUF001  (Russian test data)

import functools
import json
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, get_args
from urllib.parse import urlsplit
from uuid import UUID

import pytest
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from pypdf import PdfReader

from app.config import Settings
from app.contracts.agent import TaskProfile
from app.contracts.api.chat import ArtifactBlock, MarkdownBlock, MessageBlock
from app.contracts.common import ToolName
from app.contracts.disclosure import DisclosureCompany, DisclosureFileRow, IssuerRef
from app.contracts.tinvest import (
    TAccount,
    TCandle,
    TCoupon,
    TDividend,
    TForecasts,
    TFundamentals,
    TInstrument,
    TOperation,
    TPortfolio,
    TReportEvent,
)
from app.domains.auth.service import normalize_email
from app.gateways.fixtures import SEED, SeedUser, read_csv, read_yaml
from app.gateways.llm.fake import SCENARIOS
from app.gateways.web.fake import WebFixtures

REFERENCE = SEED.parent / "reference"
# Every bond of the seed has a nominal of 1000 in its currency; candles price it in percent.
NOMINAL = Decimal(1000)
# The currency a currency instrument of the seed holds, as T-Invest names its ISO code.
CURRENCY_OF = {
    "RUB000UTSTOM": "RUB",
    "USD000UTSTOM": "USD",
    "CNYRUB_TOM": "CNY",
    "EUR_RUB__TOM": "EUR",
}
# §9.9: a line with only an artifact placeholder.
PLACEHOLDER = re.compile(r"^\s*\[\[([cti][0-9]+)\]\]\s*$")
SYNTHETIC = "Синтетический документ"


def adapter(model: Any) -> Callable[[Path], object]:
    found: TypeAdapter[Any] = TypeAdapter(model)
    return lambda path: found.validate_python(read_yaml(path))


def candles_file(path: Path) -> list[TCandle]:
    return TypeAdapter(list[TCandle]).validate_python(read_csv(path))


def llm_file(path: Path) -> object:
    scenarios = SCENARIOS.validate_python(read_yaml(path) or [])
    tools = set(get_args(ToolName.__value__))
    for scenario in scenarios:
        if scenario.match.purpose == "classify":
            TaskProfile.model_validate(scenario.structured)
        for step in scenario.steps:
            assert step.tool_call is None or step.tool_call.name in tools, step
    return scenarios


def archive_file(path: Path) -> object:
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert names, path
        for name in names:
            assert name.endswith(".pdf"), name
            assert archive.read(name).startswith(b"%PDF-"), name
    return names


def pdf_file(path: Path) -> object:
    pages = PdfReader(path).pages
    assert pages, path
    # The text layer reads in Russian, and every page says the document is made up.
    for number, page in enumerate(pages, start=1):
        text = " ".join(page.extract_text().split())
        assert SYNTHETIC in text, f"{path.name}, page {number}"
    return pages


class BlocksArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_id: str = Field(pattern=r"^[cti][0-9]+$")
    id: UUID


class BlocksCase(BaseModel):
    """One vector of split_blocks: the text and the artifacts of a run (in creation order) give
    the blocks; `unknown` lists the placeholders dropped with an unknown_placeholder warning."""

    model_config = ConfigDict(extra="forbid")
    name: str
    text: str
    artifacts: list[BlocksArtifact]
    blocks: list[MessageBlock]
    unknown: list[str]


class BlocksCases(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    cases: list[BlocksCase]


def blocks_file(path: Path) -> BlocksCases:
    return BlocksCases.model_validate(json.loads(path.read_text(encoding="utf-8")))


# Paths inside backend/fixtures/seed, as fnmatch patterns, with the model of their contract.
VALIDATORS: dict[str, Callable[[Path], object]] = {
    "users.yaml": adapter(list[SeedUser]),
    "blocks_cases.json": blocks_file,
    "tinvest/accounts.yaml": adapter(list[TAccount]),
    "tinvest/instruments.yaml": adapter(list[TInstrument]),
    "tinvest/portfolios/*.yaml": adapter(TPortfolio),
    "tinvest/operations/*.yaml": adapter(list[TOperation]),
    "tinvest/candles/*.csv": candles_file,
    "tinvest/fundamentals.yaml": adapter(list[TFundamentals]),
    "tinvest/forecasts.yaml": adapter(dict[str, TForecasts]),
    "tinvest/dividends.yaml": adapter(dict[str, list[TDividend]]),
    "tinvest/coupons.yaml": adapter(dict[str, list[TCoupon]]),
    "tinvest/report_schedule.yaml": adapter(list[TReportEvent]),
    "llm/*.yaml": llm_file,
    "web/*.yaml": adapter(WebFixtures),
    "edisclosure/companies.yaml": adapter(list[DisclosureCompany]),
    "edisclosure/files/*.yaml": adapter(list[DisclosureFileRow]),
    "edisclosure/archives/*/*.zip": archive_file,
    "docs/*.pdf": pdf_file,
}
SEED_FILES = sorted(
    path.relative_to(SEED).as_posix() for path in SEED.rglob("*") if path.is_file()
)


@pytest.mark.parametrize("name", SEED_FILES)
def test_every_seed_file_validates_against_its_contract(name: str) -> None:
    patterns = [pattern for pattern in VALIDATORS if fnmatch(name, pattern)]

    assert len(patterns) == 1, f"{name}: no contract model checks this file"
    VALIDATORS[patterns[0]](SEED / name)


def test_every_validator_finds_its_files() -> None:
    for pattern in VALIDATORS:
        assert any(fnmatch(name, pattern) for name in SEED_FILES), pattern


def test_the_reference_issuers_validate_as_issuer_refs() -> None:
    rows = [
        {key: value or None for key, value in row.items()}
        for row in read_csv(REFERENCE / "issuers.csv")
    ]

    issuers = TypeAdapter(list[IssuerRef]).validate_python(rows)

    assert len({issuer.ticker for issuer in issuers}) == len(issuers)
    assert len({issuer.edisclosure_id for issuer in issuers}) == len(issuers)


# Users (§15.2): the owner and the demo user, one password from SEED_OWNER_PASSWORD.


@functools.cache
def users() -> list[SeedUser]:
    return TypeAdapter(list[SeedUser]).validate_python(read_yaml(SEED / "users.yaml"))


def test_the_seed_has_the_owner_and_a_demo_user_with_a_broker() -> None:
    by_role = Counter(user.role for user in users())
    [owner] = [user for user in users() if user.role == "owner"]
    brokers = [user for user in users() if user.broker_token is not None]

    assert by_role == {"owner": 1, "user": 1}
    # SEED_OWNER_EMAIL takes the place of this address; its default is the same.
    assert owner.email == Settings.model_fields["SEED_OWNER_EMAIL"].default
    assert [user.role for user in brokers] == ["user"]
    for user in users():
        assert normalize_email(user.email) == user.email


# T-Invest (§8.2): the reference data, the candles and the accounts tell one story.


@functools.cache
def instruments() -> dict[str, TInstrument]:
    found = TypeAdapter(list[TInstrument]).validate_python(
        read_yaml(SEED / "tinvest" / "instruments.yaml")
    )
    assert len({i.uid for i in found}) == len(found)
    assert len({(i.ticker, i.class_code) for i in found}) == len(found)
    by_ticker = {i.ticker: i for i in found}
    assert len(by_ticker) == len(found)
    return by_ticker


@functools.cache
def by_uid() -> dict[UUID, TInstrument]:
    return {i.uid: i for i in instruments().values()}


@functools.cache
def candles(ticker: str) -> list[TCandle]:
    return candles_file(SEED / "tinvest" / "candles" / f"{ticker}.csv")


@functools.cache
def last_day() -> date:
    return candles("IMOEX")[-1].time.date()


def tinvest(name: str, model: Any) -> Any:
    return adapter(model)(SEED / "tinvest" / name)


def test_the_instruments_cover_the_imoex_shares_bonds_funds_and_currencies() -> None:
    kinds = Counter(i.instrument_type for i in instruments().values())
    classes = Counter(i.class_code for i in instruments().values())

    assert 25 <= len(instruments()) <= 35  # about thirty (§15.2)
    assert kinds["share"] >= 15
    assert classes["TQOB"] >= 2  # OFZ
    assert classes["TQCB"] >= 1  # corporate bonds
    assert kinds["etf"] >= 2
    assert set(CURRENCY_OF) <= set(instruments())
    assert instruments()["IMOEX"].instrument_type == "index"


def test_every_share_has_a_row_in_the_reference_issuers() -> None:
    tickers = {row["ticker"] for row in read_csv(REFERENCE / "issuers.csv")}
    shares = {t for t, i in instruments().items() if i.instrument_type == "share"}

    assert shares <= tickers


def test_every_instrument_but_the_ruble_has_two_years_of_daily_candles() -> None:
    files = {path.stem for path in (SEED / "tinvest" / "candles").glob("*.csv")}

    assert files == set(instruments()) - {"RUB000UTSTOM"}
    for ticker in files:
        rows = candles(ticker)
        days = [candle.time.date() for candle in rows]
        assert days == sorted(set(days)), ticker
        assert all(day.weekday() < 5 for day in days), ticker
        assert days[0] <= last_day() - timedelta(days=730), ticker
        assert days[-1] == last_day(), ticker
        for candle in rows:
            assert candle.low <= min(candle.open, candle.close), (ticker, candle)
            assert max(candle.open, candle.close) <= candle.high, (ticker, candle)
            assert candle.volume >= 0


def test_the_reference_data_names_known_instruments_of_the_right_type() -> None:
    def types(tickers: object) -> set[str]:
        assert isinstance(tickers, dict)
        return {instruments()[ticker].instrument_type for ticker in tickers}

    fundamentals = tinvest("fundamentals.yaml", list[TFundamentals])
    assets = {i.asset_uid: i for i in instruments().values() if i.asset_uid is not None}
    reports = tinvest("report_schedule.yaml", list[TReportEvent])

    assert types(tinvest("forecasts.yaml", dict[str, TForecasts])) == {"share"}
    assert types(tinvest("dividends.yaml", dict[str, list[TDividend]])) <= {"share", "etf"}
    assert types(tinvest("coupons.yaml", dict[str, list[TCoupon]])) == {"bond"}
    assert {assets[f.asset_uid].instrument_type for f in fundamentals} == {"share"}
    assert len({f.asset_uid for f in fundamentals}) == len(fundamentals)
    assert {by_uid()[event.instrument_uid].instrument_type for event in reports} == {"share"}


def test_every_bond_has_its_coupons_and_every_payout_keeps_its_dates_in_order() -> None:
    coupons: dict[str, list[TCoupon]] = tinvest("coupons.yaml", dict[str, list[TCoupon]])
    dividends: dict[str, list[TDividend]] = tinvest(
        "dividends.yaml", dict[str, list[TDividend]]
    )
    bonds = {t for t, i in instruments().items() if i.instrument_type == "bond"}

    assert set(coupons) == bonds
    for ticker, rows in coupons.items():
        assert [c.number for c in rows] == sorted({c.number for c in rows}), ticker
        assert [c.coupon_date for c in rows] == sorted({c.coupon_date for c in rows}), ticker
        for coupon in rows:
            if coupon.amount is not None:
                assert coupon.amount.currency == instruments()[ticker].currency
    for ticker, rows in dividends.items():
        for dividend in rows:
            assert dividend.last_buy_date <= dividend.record_date <= dividend.payment_date
            assert dividend.amount.currency == instruments()[ticker].currency


@functools.cache
def accounts() -> list[TAccount]:
    found: list[TAccount] = tinvest("accounts.yaml", list[TAccount])
    return found


def operations(account: str) -> list[TOperation]:
    found: list[TOperation] = tinvest(f"operations/{account}.yaml", list[TOperation])
    return found


def portfolio(account: str) -> TPortfolio:
    found: TPortfolio = tinvest(f"portfolios/{account}.yaml", TPortfolio)
    return found


def test_the_demo_has_a_brokerage_account_and_an_iis_both_read_only() -> None:
    folders = {
        folder: {path.stem for path in (SEED / "tinvest" / folder).glob("*.yaml")}
        for folder in ("portfolios", "operations")
    }
    ids = {account.id for account in accounts()}

    assert sorted(account.type for account in accounts()) == ["broker", "iis"]
    assert {account.access_level for account in accounts()} == {"read_only"}
    assert folders == {"portfolios": ids, "operations": ids}
    for account in accounts():
        assert portfolio(account.id).account_id == account.id


@pytest.mark.parametrize("account", ["2000000001", "2000000002"])
def test_the_operations_span_two_years_and_name_known_instruments(account: str) -> None:
    found = operations(account)
    moments = [op.date for op in found]

    assert len({op.id for op in found}) == len(found)
    assert (max(moments) - min(moments)).days >= 600
    for op in found:
        assert op.instrument_uid is None or op.instrument_uid in by_uid(), op
        if op.kind in {"buy", "sell"}:
            assert op.quantity is not None and op.quantity > 0, op
            assert op.price is not None, op
            # The payment of a trade is its price times its quantity, in the price currency.
            sign = -1 if op.kind == "buy" else 1
            assert op.payment.amount == sign * op.price.amount * op.quantity, op
            assert op.payment.currency == op.price.currency, op


def replay(account: str) -> dict[UUID, Decimal]:
    """Positions after the operations: instruments by trades, money by payments."""
    held: defaultdict[UUID, Decimal] = defaultdict(Decimal)
    cash: defaultdict[str, Decimal] = defaultdict(Decimal)
    for op in operations(account):
        cash[op.payment.currency] += op.payment.amount
        if op.kind not in {"buy", "sell"}:
            continue
        assert op.instrument_uid is not None and op.quantity is not None
        quantity = op.quantity if op.kind == "buy" else -op.quantity
        instrument = by_uid()[op.instrument_uid]
        if instrument.instrument_type == "currency":
            cash[CURRENCY_OF[instrument.ticker]] += quantity
        else:
            held[op.instrument_uid] += quantity
    for ticker, currency in CURRENCY_OF.items():
        held[instruments()[ticker].uid] += cash[currency]
    return {uid: quantity for uid, quantity in held.items() if quantity}


@pytest.mark.parametrize("account", ["2000000001", "2000000002"])
def test_the_positions_replay_the_operations(account: str) -> None:
    positions = portfolio(account).positions

    assert len({p.instrument_uid for p in positions}) == len(positions)
    assert {p.instrument_uid: p.quantity for p in positions} == replay(account)


def rate(currency: str) -> Decimal:
    """Rubles for a unit of the currency at the last close."""
    if currency == "RUB":
        return Decimal(1)
    [ticker] = [t for t, c in CURRENCY_OF.items() if c == currency]
    return candles(ticker)[-1].close


@pytest.mark.parametrize("account", ["2000000001", "2000000002"])
def test_the_last_closes_price_the_positions_and_sum_to_the_total(account: str) -> None:
    found = portfolio(account)
    total = Decimal(0)

    for position in found.positions:
        instrument = by_uid()[position.instrument_uid]
        assert (position.figi, position.instrument_type) == (
            instrument.figi,
            instrument.instrument_type,
        )
        assert position.current_price is not None and position.average_price is not None
        close = (
            Decimal(1) if instrument.ticker == "RUB000UTSTOM" else candles(instrument.ticker)[-1].close
        )
        if instrument.instrument_type == "bond":
            assert position.current_price.amount == close * NOMINAL / 100, instrument.ticker
            assert position.accrued_interest is not None, instrument.ticker
        else:
            assert position.current_price.amount == close, instrument.ticker
            assert position.accrued_interest is None, instrument.ticker
        currency = position.current_price.currency
        assert currency == ("RUB" if instrument.instrument_type == "currency" else instrument.currency)
        accrued = position.accrued_interest.amount if position.accrued_interest else Decimal(0)
        total += (position.current_price.amount + accrued) * position.quantity * rate(currency)

    assert found.total.currency == "RUB"
    assert found.total.amount == sum(m.amount for m in found.total_by_type.values())
    assert abs(found.total.amount - total) <= Decimal("0.01") * len(found.total_by_type)


# Web (§8.4): synthetic answers on example domains only (RFC 2606).


RESERVED_HOST = re.compile(r"(^|\.)(example\.(com|net|org)|[a-z0-9-]+\.(example|test))$")


def test_the_web_fixtures_stay_on_reserved_example_domains() -> None:
    queries: list[str] = []
    urls: list[str] = []
    for path in sorted((SEED / "web").glob("*.yaml")):
        found = TypeAdapter(WebFixtures).validate_python(read_yaml(path))
        queries += [" ".join(s.query.casefold().split()) for s in found.search]
        urls += [str(hit.url) for s in found.search for hit in s.hits]
        urls += [str(image.url) for s in found.search for image in s.images]
        urls += [str(page.url) for page in found.extract]
        urls += [str(c.url) for c in found.crawl]
        urls += [str(page.url) for c in found.crawl for page in c.pages]
        urls += [str(m.url) for m in found.map] + [url for m in found.map for url in m.urls]

    # The fake matches a search by its normalized query: two entries would shadow each other.
    assert len(set(queries)) == len(queries)
    for url in urls:
        assert RESERVED_HOST.search(urlsplit(url).hostname or ""), url


# e-disclosure (§8.5): the cards, the rows of their sections and the archives agree.


@functools.cache
def file_rows() -> dict[int, list[DisclosureFileRow]]:
    rows = TypeAdapter(list[DisclosureFileRow])
    return {
        int(path.stem): rows.validate_python(read_yaml(path))
        for path in sorted((SEED / "edisclosure" / "files").glob("*.yaml"))
    }


def test_the_rows_belong_to_known_companies_and_point_at_their_files() -> None:
    companies = TypeAdapter(list[DisclosureCompany]).validate_python(
        read_yaml(SEED / "edisclosure" / "companies.yaml")
    )

    assert set(file_rows()) <= {company.company_id for company in companies}
    for company_id, rows in file_rows().items():
        for row in rows:
            assert f"id={company_id}&" in row.page_url, row
            assert row.download_url.endswith(f"Fileid={row.file_id}"), row


def test_every_archive_belongs_to_a_row_and_every_document_sits_in_an_archive() -> None:
    rows = {row.file_id: row for found in file_rows().values() for row in found}
    inside: set[bytes] = set()

    for folder in (SEED / "edisclosure" / "archives").iterdir():
        [archive] = folder.iterdir()
        row = rows[int(folder.name)]
        assert archive.suffix == f".{row.file_ext}", archive
        with zipfile.ZipFile(archive) as found:
            inside |= {found.read(name) for name in found.namelist()}

    for document in (SEED / "docs").glob("*.pdf"):
        assert document.read_bytes() in inside, document.name


# split_blocks vectors (§9.9): the oracle below spells out the rules the vectors encode.


def reference_split(case: BlocksCase) -> tuple[list[MessageBlock], list[str]]:
    ids = {artifact.local_id: artifact.id for artifact in case.artifacts}
    blocks: list[MessageBlock] = []
    unknown: list[str] = []
    shown: set[str] = set()
    lines: list[str] = []

    def flush() -> None:
        if text := "\n".join(lines).strip():
            blocks.append(MarkdownBlock(text=text))
        lines.clear()

    for line in case.text.split("\n"):
        found = PLACEHOLDER.match(line)
        if found is None:
            lines.append(line)
            continue
        flush()
        local_id = found.group(1)
        if local_id not in ids:
            unknown.append(local_id)
        elif local_id not in shown:
            shown.add(local_id)
            blocks.append(ArtifactBlock(artifact_id=ids[local_id]))
    flush()
    blocks += [ArtifactBlock(artifact_id=a.id) for a in case.artifacts if a.local_id not in shown]
    return blocks, unknown


@functools.cache
def blocks_cases() -> BlocksCases:
    return blocks_file(SEED / "blocks_cases.json")


def test_the_blocks_vectors_cover_the_rules_of_split_blocks() -> None:
    names = [case.name for case in blocks_cases().cases]

    assert len(set(names)) == len(names)
    assert len(names) >= 10


@pytest.mark.parametrize("case", blocks_cases().cases, ids=lambda case: case.name)
def test_a_blocks_vector_follows_the_rules_of_split_blocks(case: BlocksCase) -> None:
    artifact_ids = [b.artifact_id for b in case.blocks if isinstance(b, ArtifactBlock)]
    texts = [b.text for b in case.blocks if isinstance(b, MarkdownBlock)]

    # Every artifact of the run shows up once; no block keeps a placeholder line.
    assert sorted(artifact_ids, key=str) == sorted((a.id for a in case.artifacts), key=str)
    assert all(text == text.strip() and text for text in texts)
    assert not any(PLACEHOLDER.match(line) for text in texts for line in text.split("\n"))
    assert reference_split(case) == (case.blocks, case.unknown)
