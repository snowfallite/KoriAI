"""Seed fixtures generator (tech.md §15.2, S1-10): synthetic, deterministic, coherent data.

Candles follow a market factor (the IMOEX index); the trades and payouts of each account make its
operations, the operations make the positions, the last closes price the portfolios. The three
documents of seed/docs are made up as well and sit in the e-disclosure archives of the rows they
belong to. The instruments of S1-09 keep their candles bit for bit: their noise comes from the
S1-09 random stream, every added instrument draws from its own.

Run by hand from the repo root; it rewrites backend/fixtures/seed/tinvest and seed/docs and
writes the three archives of the documents:

    uv run --no-project --with pyyaml==6.0.3 --with reportlab==5.0.1 --with matplotlib==3.11.2
        python scripts/generate_seed.py
"""

# ruff: noqa: RUF001, S101, S311  (Russian data; asserts guard the data; random makes noise)

import csv
import io
import math
import random
import sys
import uuid
import zipfile
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import matplotlib as mpl
import yaml
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "backend" / "fixtures" / "seed"
TINVEST = SEED / "tinvest"
NS = uuid.UUID("6f1c0a52-3a4b-4c77-9e55-0b8d1f2c7a10")
START, END = date(2024, 10, 1), date(2026, 10, 2)
DAYS = [d for d in (START + timedelta(n) for n in range((END - START).days + 1)) if d.weekday() < 5]
TAX = Decimal("0.13")
FEE = Decimal("0.0005")
NOMINAL = Decimal(1000)
SYNTHETIC = "Синтетические данные сида (S1-10), не рыночные."

type Bar = dict[str, Any]


@dataclass(frozen=True)
class Spec:
    ticker: str
    class_code: str
    kind: str
    name: str
    lot: int
    isin: str | None
    figi: str | None
    sector: str | None
    country: str | None
    exchange: str
    logo: str | None
    color: str | None
    currency: str
    start: float | None  # first close; a bond in percent of its nominal
    beta: float  # to the market factor
    sigma: float  # daily noise of its own
    places: int
    drift: float = 0.0  # daily, the added instruments only


def spec(*fields: Any) -> Spec:
    return Spec(*fields)


# fmt: off
# The eleven instruments of S1-09, in the order its random stream visits them.
LEGACY = [
    spec("SBER", "TQBR", "share", "Сбербанк", 10, "RU0009029540", "BBG004730N88", "financial", "RU", "MOEX", "sber", "#21A038", "RUB", 270, 1.1, 0.009, 2),  # noqa: E501
    spec("GAZP", "TQBR", "share", "Газпром", 10, "RU0007661625", "BBG004730RP0", "energy", "RU", "MOEX", "gazprom", "#0079C2", "RUB", 130, 0.9, 0.013, 2),  # noqa: E501
    spec("LKOH", "TQBR", "share", "ЛУКОЙЛ", 1, "RU0009024277", "BBG004731032", "energy", "RU", "MOEX", "lukoil", "#ED1C24", "RUB", 7000, 0.8, 0.009, 1),  # noqa: E501
    spec("YDEX", "TQBR", "share", "Яндекс", 1, "RU000A107T19", "TCS00A107T19", "it", "RU", "MOEX", "yandex", "#FC3F1D", "RUB", 4000, 1.2, 0.014, 1),  # noqa: E501
    spec("SU26238RMFS4", "TQOB", "bond", "ОФЗ 26238", 1, "RU000A1038V6", "TCS00A1038V6", "government", "RU", "MOEX", "minfin", "#1E3A8A", "RUB", 58.0, 0.2, 0.004, 3),  # noqa: E501
    spec("RU000A10B9Q9", "TQCB", "bond", "РЖД 001Р-29R", 1, "RU000A10B9Q9", "TCS00A10B9Q9", "transport", "RU", "MOEX", "rzd", "#E21A1A", "RUB", 99.5, 0.05, 0.0015, 2),  # noqa: E501
    spec("TMOS", "TQTF", "etf", "Т-Капитал Индекс МосБиржи", 1, "RU000A101X76", "TCS60A101X76", "other", "RU", "MOEX", "tcapital", "#FFDD2D", "RUB", 7.0, 1.0, 0.001, 4),  # noqa: E501
    spec("USD000UTSTOM", "CETS", "currency", "Доллар США", 1000, None, "BBG0013HGFT4", None, None, "FX", "usd", "#4A4A4A", "RUB", 96.0, 0.0, 0.006, 4),  # noqa: E501
    spec("CNYRUB_TOM", "CETS", "currency", "Китайский юань", 1000, None, "BBG0013HRTL0", None, None, "FX", "cny", "#D32F2F", "RUB", 13.3, 0.0, 0.005, 4),  # noqa: E501
    spec("RUB000UTSTOM", "CETS", "currency", "Российский рубль", 1, None, "RUB000UTSTOM", None, None, "FX", "rub", "#2E7D32", "RUB", None, 0.0, 0.0, 2),  # noqa: E501
    spec("IMOEX", "INDX", "index", "Индекс МосБиржи", 1, None, None, None, "RU", "MOEX", "imoex", "#003366", "RUB", 2900, 1.0, 0.0, 2),  # noqa: E501
]
# S1-10 brings the seed to about thirty instruments (§15.2). The yuan bond has no logo: the UI
# shows initials for it.
ADDED = [
    spec("GMKN", "TQBR", "share", "Норильский никель", 10, "RU0007288411", "BBG004731489", "materials", "RU", "MOEX", "nornickel", "#1E61A8", "RUB", 130.0, 0.9, 0.011, 2, -0.0001),  # noqa: E501
    spec("ROSN", "TQBR", "share", "Роснефть", 1, "RU000A0J2Q06", "BBG004731354", "energy", "RU", "MOEX", "rosneft", "#FDB913", "RUB", 520.0, 0.9, 0.010, 2),  # noqa: E501
    spec("NVTK", "TQBR", "share", "НОВАТЭК", 1, "RU000A0DKVS5", "BBG00475KKY8", "energy", "RU", "MOEX", "novatek", "#00A3E0", "RUB", 1000.0, 0.9, 0.012, 1),  # noqa: E501
    spec("TATN", "TQBR", "share", "Татнефть", 1, "RU0009033591", "BBG004RVFFC0", "energy", "RU", "MOEX", "tatneft", "#0D7C3D", "RUB", 650.0, 0.8, 0.009, 1, 0.0001),  # noqa: E501
    spec("MGNT", "TQBR", "share", "Магнит", 1, "RU000A0JKQU8", "BBG004RVFCY3", "consumer", "RU", "MOEX", "magnit", "#E30613", "RUB", 6200.0, 0.8, 0.012, 1, -0.0003),  # noqa: E501
    spec("MTSS", "TQBR", "share", "МТС", 10, "RU0007775219", "BBG004S681W1", "telecom", "RU", "MOEX", "mts", "#E30611", "RUB", 250.0, 0.7, 0.009, 2, -0.0001),  # noqa: E501
    spec("PLZL", "TQBR", "share", "Полюс", 1, "RU000A0JNAA8", "BBG000R607Y3", "materials", "RU", "MOEX", "polyus", "#C9A227", "RUB", 1650.0, 0.5, 0.012, 1, 0.0007),  # noqa: E501
    spec("CHMF", "TQBR", "share", "Северсталь", 1, "RU0009046510", "BBG00475K6C3", "materials", "RU", "MOEX", "severstal", "#00508F", "RUB", 1300.0, 0.9, 0.011, 1, -0.0002),  # noqa: E501
    spec("NLMK", "TQBR", "share", "НЛМК", 10, "RU0009046452", "BBG004S681B4", "materials", "RU", "MOEX", "nlmk", "#003B7A", "RUB", 170.0, 0.9, 0.011, 2, -0.0002),  # noqa: E501
    spec("ALRS", "TQBR", "share", "АЛРОСА", 10, "RU0007252813", "BBG004S68B31", "materials", "RU", "MOEX", "alrosa", "#0072BC", "RUB", 70.0, 0.8, 0.012, 2, -0.0004),  # noqa: E501
    spec("MOEX", "TQBR", "share", "Московская биржа", 10, "RU000A0JR4A1", "BBG004730JJ5", "financial", "RU", "MOEX", "moex", "#C8102E", "RUB", 215.0, 0.8, 0.010, 2),  # noqa: E501
    spec("VTBR", "TQBR", "share", "ВТБ", 1, "RU000A0JP5V6", "BBG004730ZJ9", "financial", "RU", "MOEX", "vtb", "#002882", "RUB", 90.0, 1.2, 0.013, 2, -0.0001),  # noqa: E501
    spec("AFLT", "TQBR", "share", "Аэрофлот", 10, "RU0009062285", "BBG004S683W7", "industrials", "RU", "MOEX", "aeroflot", "#0B3D91", "RUB", 55.0, 1.1, 0.013, 2, 0.0001),  # noqa: E501
    spec("PHOR", "TQBR", "share", "ФосАгро", 1, "RU000A0JRKT8", "BBG004S689R0", "materials", "RU", "MOEX", "phosagro", "#009A44", "RUB", 6600.0, 0.6, 0.009, 0, 0.0001),  # noqa: E501
    spec("SU29024RMFS5", "TQOB", "bond", "ОФЗ 29024", 1, "RU000A107MK6", "TCS00A107MK6", "government", "RU", "MOEX", "minfin", "#1E3A8A", "RUB", 99.6, 0.0, 0.0008, 2),  # noqa: E501
    spec("RU000A108TS3", "TQCB", "bond", "Норникель БО-001Р-11-CNY", 1, "RU000A108TS3", "TCS00A108TS3", "materials", "RU", "MOEX", None, None, "CNY", 98.6, 0.0, 0.0015, 2),  # noqa: E501
    spec("LQDT", "TQTF", "etf", "ВИМ - Ликвидность", 1, "RU000A1014L8", "TCS00A1014L8", "other", "RU", "MOEX", "vim", "#5A2D82", "RUB", 1.62, 0.0, 0.00004, 4, 0.00055),  # noqa: E501
    spec("TGLD", "TQTF", "etf", "Т-Капитал Золото", 1, "RU000A101X50", "TCS10A101X50", "other", "RU", "MOEX", "tcapital", "#FFDD2D", "RUB", 8.2, 0.0, 0.008, 2, 0.0005),  # noqa: E501
    spec("EUR_RUB__TOM", "CETS", "currency", "Евро", 1000, None, "BBG0013HJJ31", None, None, "FX", "eur", "#1F3A93", "RUB", 105.0, 0.0, 0.006, 4),  # noqa: E501
]
SPECS = {s.ticker: s for s in LEGACY + ADDED}
# The money a currency instrument holds, by its ISO code.
CURRENCY_OF = {"RUB000UTSTOM": "RUB", "USD000UTSTOM": "USD", "CNYRUB_TOM": "CNY", "EUR_RUB__TOM": "EUR"}  # noqa: E501
TICKER_OF = {currency: ticker for ticker, currency in CURRENCY_OF.items()}
# fmt: on

# fmt: off
# ticker: [(coupon day, amount of a bond)]; None: a floater whose coupon is not set yet.
COUPONS: dict[str, list[tuple[date, Decimal | None]]] = {
    "SU26238RMFS4": [
        (d, Decimal("35.40"))
        for d in (
            date(2024, 6, 5), date(2024, 12, 4), date(2025, 6, 4), date(2025, 12, 3),
            date(2026, 6, 3), date(2026, 12, 2), date(2027, 6, 2),
        )
    ],
    "RU000A10B9Q9": [
        (d, Decimal("41.14"))
        for d in (
            date(2024, 9, 20), date(2024, 12, 20), date(2025, 3, 21), date(2025, 6, 20),
            date(2025, 9, 19), date(2025, 12, 19), date(2026, 3, 20), date(2026, 6, 19),
            date(2026, 9, 18), date(2026, 12, 18), date(2027, 3, 19),
        )
    ],
    "SU29024RMFS5": [
        (date(2024, 9, 11), Decimal("112.40")), (date(2025, 3, 12), Decimal("105.21")),
        (date(2025, 9, 10), Decimal("98.74")), (date(2026, 3, 11), Decimal("87.29")),
        (date(2026, 9, 9), Decimal("79.52")), (date(2027, 3, 10), Decimal("74.80")),
        (date(2027, 9, 8), None),
    ],
    "RU000A108TS3": [
        (d, Decimal("37.40"))
        for d in (
            date(2024, 8, 20), date(2025, 2, 18), date(2025, 8, 19), date(2026, 2, 17),
            date(2026, 8, 18), date(2027, 2, 16), date(2027, 8, 17),
        )
    ],
}
# ticker: [(record day, payment day, per share)]; the ones after END are announced only.
DIVIDENDS: dict[str, list[tuple[date, date, str]]] = {
    "SBER": [(date(2025, 7, 18), date(2025, 7, 25), "34.84"), (date(2026, 7, 17), date(2026, 7, 24), "37.50")],  # noqa: E501
    "LKOH": [
        (date(2024, 12, 17), date(2025, 1, 10), "514"),
        (date(2025, 6, 3), date(2025, 6, 24), "541"),
        (date(2025, 12, 16), date(2026, 1, 12), "397"),
        (date(2026, 6, 2), date(2026, 6, 23), "514"),
        (date(2026, 12, 16), date(2027, 1, 11), "420"),
    ],
    "YDEX": [(date(2025, 10, 6), date(2025, 10, 20), "80"), (date(2026, 4, 7), date(2026, 4, 21), "110")],  # noqa: E501
    "GMKN": [(date(2025, 6, 17), date(2025, 7, 8), "5.25"), (date(2026, 6, 16), date(2026, 7, 7), "4.80")],  # noqa: E501
    "ROSN": [
        (date(2025, 1, 17), date(2025, 2, 7), "36.47"),
        (date(2025, 7, 14), date(2025, 8, 4), "14.68"),
        (date(2026, 1, 16), date(2026, 2, 6), "11.56"),
        (date(2026, 7, 13), date(2026, 8, 3), "20.12"),
    ],
    "TATN": [
        (date(2025, 7, 8), date(2025, 7, 29), "60.04"),
        (date(2026, 1, 9), date(2026, 1, 30), "41.30"),
        (date(2026, 7, 7), date(2026, 7, 28), "52.80"),
    ],
    "MOEX": [(date(2025, 5, 15), date(2025, 6, 5), "26.11"), (date(2026, 5, 14), date(2026, 6, 4), "23.40")],  # noqa: E501
    "MTSS": [(date(2025, 7, 8), date(2025, 7, 29), "35"), (date(2026, 7, 7), date(2026, 7, 28), "35")],  # noqa: E501
    "PLZL": [(date(2025, 10, 10), date(2025, 10, 31), "70.06"), (date(2026, 4, 24), date(2026, 5, 15), "76.80")],  # noqa: E501
    "NVTK": [
        (date(2025, 5, 6), date(2025, 5, 27), "46.65"),
        (date(2025, 10, 10), date(2025, 10, 31), "35.50"),
        (date(2026, 5, 5), date(2026, 5, 26), "48.10"),
    ],
    "CHMF": [
        (date(2025, 6, 17), date(2025, 7, 8), "36.04"),
        (date(2026, 6, 16), date(2026, 7, 7), "31.20"),
        (date(2026, 12, 15), date(2027, 1, 12), "18.50"),
    ],
    "NLMK": [(date(2025, 6, 10), date(2025, 7, 1), "6"), (date(2026, 6, 9), date(2026, 6, 30), "7.20")],  # noqa: E501
    "PHOR": [
        (date(2025, 6, 9), date(2025, 6, 30), "387"),
        (date(2025, 12, 8), date(2025, 12, 29), "171"),
        (date(2026, 6, 8), date(2026, 6, 29), "324"),
    ],
    "MGNT": [(date(2025, 6, 3), date(2025, 6, 24), "315"), (date(2026, 6, 2), date(2026, 6, 23), "412")],  # noqa: E501
    "ALRS": [(date(2025, 7, 15), date(2025, 8, 5), "2.40"), (date(2026, 7, 14), date(2026, 8, 4), "3.10")],  # noqa: E501
    "VTBR": [(date(2025, 7, 11), date(2025, 8, 1), "25.58")],
    "AFLT": [(date(2025, 7, 11), date(2025, 8, 1), "3.68"), (date(2026, 7, 10), date(2026, 7, 31), "4.10")],  # noqa: E501
}
# Inputs and outputs of rubles, then trades (a negative quantity sells).
ACCOUNTS: dict[str, dict[str, list[Any]]] = {
    "2000000001": {
        "cash": [
            (date(2024, 10, 1), "input", Decimal(1_000_000)),
            (date(2025, 2, 3), "input", Decimal(1_400_000)),
            (date(2025, 9, 1), "input", Decimal(600_000)),
            (date(2026, 5, 13), "input", Decimal(200_000)),
            (date(2026, 8, 3), "output", Decimal(-100_000)),
        ],
        "trades": [
            (date(2024, 10, 2), "SBER", 300), (date(2024, 10, 2), "GAZP", 1000),
            (date(2024, 10, 2), "LKOH", 20), (date(2024, 10, 3), "SU26238RMFS4", 300),
            (date(2024, 10, 3), "TMOS", 10000), (date(2025, 2, 4), "GMKN", 1000),
            (date(2025, 2, 4), "ROSN", 200), (date(2025, 2, 4), "NVTK", 100),
            (date(2025, 2, 4), "TATN", 150), (date(2025, 2, 4), "MOEX", 500),
            (date(2025, 2, 5), "SU29024RMFS5", 200), (date(2025, 2, 5), "LQDT", 100000),
            (date(2025, 3, 12), "USD000UTSTOM", 1000), (date(2025, 4, 15), "VTBR", 1000),
            (date(2025, 6, 10), "SBER", 100), (date(2025, 9, 2), "PLZL", 50),
            (date(2025, 9, 2), "MTSS", 400), (date(2025, 9, 2), "TGLD", 20000),
            (date(2025, 11, 20), "VTBR", -1000), (date(2026, 2, 10), "LQDT", -50000),
            (date(2026, 3, 16), "GAZP", -400), (date(2026, 5, 14), "CHMF", 60),
            (date(2026, 5, 14), "AFLT", 1000),
        ],
    },
    "2000000002": {
        "cash": [
            (date(2024, 10, 10), "input", Decimal(400_000)),
            (date(2025, 10, 10), "input", Decimal(150_000)),
            (date(2026, 1, 15), "input", Decimal(500_000)),
        ],
        "trades": [
            (date(2024, 10, 11), "YDEX", 40), (date(2024, 10, 11), "RU000A10B9Q9", 150),
            (date(2024, 10, 11), "CNYRUB_TOM", 5000), (date(2024, 10, 14), "RU000A108TS3", 3),
            (date(2025, 10, 13), "YDEX", 20), (date(2026, 1, 16), "MGNT", 10),
            (date(2026, 1, 16), "PHOR", 10), (date(2026, 1, 16), "MTSS", 600),
            (date(2026, 1, 16), "ALRS", 1000), (date(2026, 1, 16), "NLMK", 300),
        ],
    },
}
# fmt: on
TEXTS = {
    "input": "Пополнение брокерского счёта",
    "output": "Вывод денежных средств",
    "buy": "Покупка ценных бумаг",
    "sell": "Продажа ценных бумаг",
    "commission": "Удержание комиссии за операцию",
    "dividend": "Выплата дивидендов",
    "coupon": "Выплата купонов",
    "dividend_tax": "Удержание налога по дивидендам",
    "coupon_tax": "Удержание НДФЛ по купонам",
}


def uid(kind: str, ticker: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}:{ticker}"))


def q(value: float | Decimal, places: int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP)


def s(value: Decimal) -> str:
    return format(value.normalize(), "f") if value != 0 else "0"


def money(amount: Decimal, currency: str = "RUB") -> dict[str, str]:
    return {"amount": s(amount), "currency": currency}


def say(line: str) -> None:
    sys.stdout.write(line + "\n")


def dump(path: Path, data: object, comment: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
    path.write_text(f"# {comment}\n# {SYNTHETIC}\n{text}", encoding="utf-8", newline="\n")


# Candles


def ohlc(
    rng: random.Random, ticker: str, series: list[float], wick: float, places: int
) -> list[Bar]:
    rows, prev = [], series[0]
    for day, close in zip(DAYS, series, strict=True):
        open_ = prev * (1 + rng.gauss(0, wick / 3))
        high = max(open_, close) * (1 + abs(rng.gauss(0, wick / 2)))
        low = min(open_, close) * (1 - abs(rng.gauss(0, wick / 2)))
        volume = 0 if ticker == "IMOEX" else int(rng.lognormvariate(12, 0.5))
        rows.append(
            {
                "time": datetime.combine(day, time(7), UTC),
                "open": q(open_, places),
                "high": q(high, places),
                "low": q(low, places),
                "close": q(close, places),
                "volume": volume,
            }
        )
        prev = close
    return rows


def candles() -> dict[str, list[Bar]]:
    """The S1-09 stream for its instruments, then a stream per added instrument."""
    rng = random.Random(20260929)
    market = [rng.gauss(0.0002, 0.011) for _ in DAYS]
    closes: dict[str, list[float]] = {}
    index = [2900.0]
    for r in market[1:]:
        index.append(index[-1] * math.exp(r))
    closes["IMOEX"] = index
    closes["TMOS"] = [v / 414.3 * (1 + rng.gauss(0, 0.0005)) for v in index]
    for item in LEGACY:
        if item.ticker in closes or item.start is None:
            continue
        price, series = float(item.start), [float(item.start)]
        for r in market[1:]:
            if item.kind == "bond":  # a bond pulls back to its level
                price += (
                    0.02 * (item.start - price)
                    + rng.gauss(0, item.sigma) * price
                    + item.beta * r * price * 0.1
                )
            else:
                price *= math.exp(item.beta * r + rng.gauss(0, item.sigma))
            series.append(price)
        closes[item.ticker] = series
    bars = {
        ticker: ohlc(rng, ticker, series, max(SPECS[ticker].sigma, 0.004), SPECS[ticker].places)
        for ticker, series in closes.items()
    }
    for item in ADDED:
        assert item.start is not None
        own = random.Random(f"kori-seed:{item.ticker}")
        price, series = item.start, [item.start]
        for r in market[1:]:
            if item.kind == "bond":
                price += 0.03 * (item.start - price) + own.gauss(0, item.sigma) * price
            else:
                price *= math.exp(item.drift + item.beta * r + own.gauss(0, item.sigma))
            series.append(price)
        wick = max(item.sigma, 0.0005)
        bars[item.ticker] = ohlc(own, item.ticker, series, wick, item.places)
    return bars


def close_on(rows: list[Bar], day: date) -> Decimal:
    found: Decimal = [r["close"] for r in rows if r["time"].date() <= day][-1]
    return found


def unit_price(ticker: str, day: date, bars: dict[str, list[Bar]]) -> Decimal:
    """The price of one unit in its currency: a bond trades in percent of its nominal."""
    price = close_on(bars[ticker], day)
    return q(price * NOMINAL / 100, 2) if SPECS[ticker].kind == "bond" else price


def accrued(ticker: str, day: date) -> Decimal:
    """Accrued interest of one bond: the coming coupon, pro rata (a floater knows it)."""
    rows = COUPONS[ticker]
    last = max(d for d, _ in rows if d <= day)
    coming, amount = min((d, a) for d, a in rows if d > day)
    assert amount is not None, ticker
    return q(amount * (day - last).days / (coming - last).days, 2)


def write_candles(bars: dict[str, list[Bar]]) -> None:
    folder = TINVEST / "candles"
    folder.mkdir(parents=True, exist_ok=True)
    for ticker, rows in bars.items():
        with (folder / f"{ticker}.csv").open("w", encoding="utf-8", newline="\n") as out:
            writer = csv.writer(out, lineterminator="\n")
            writer.writerow(["time", "open", "high", "low", "close", "volume", "is_complete"])
            for r in rows:
                writer.writerow(
                    [
                        r["time"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                        s(r["open"]),
                        s(r["high"]),
                        s(r["low"]),
                        s(r["close"]),
                        r["volume"],
                        "true",
                    ]
                )


def instruments() -> list[dict[str, Any]]:
    return [
        {
            "uid": uid("instrument", item.ticker),
            "figi": item.figi,
            "ticker": item.ticker,
            "class_code": item.class_code,
            "isin": item.isin,
            "name": item.name,
            "instrument_type": item.kind,
            "currency": item.currency,
            "lot": item.lot,
            "asset_uid": None if item.kind == "index" else uid("asset", item.ticker),
            "brand_uid": uid("brand", item.ticker),
            "logo_name": f"{item.logo}.png" if item.logo else None,
            "brand_color": item.color,
            "sector": item.sector,
            "country_iso": item.country,
            "exchange": item.exchange,
            "for_qual_only": False,
        }
        for item in LEGACY + ADDED
    ]


# Accounts


@dataclass
class Event:
    moment: datetime
    kind: str
    ticker: str | None
    quantity: int | None
    price: Decimal | None
    payment: Decimal
    currency: str
    text: str


def account_events(plan: dict[str, list[Any]], bars: dict[str, list[Bar]]) -> list[Event]:
    trades = sorted(plan["trades"])

    def held_on(ticker: str, day: date) -> int:
        return sum(n for d, t, n in trades if t == ticker and d <= day)

    events = [
        Event(
            datetime.combine(day, time(7), UTC), kind, None, None, None, amount, "RUB", TEXTS[kind]
        )
        for day, kind, amount in plan["cash"]
    ]
    for day, ticker, quantity in trades:
        item = SPECS[ticker]
        currency = "RUB" if item.kind == "currency" else item.currency
        price = unit_price(ticker, day, bars)
        amount = price * abs(quantity)
        moment = datetime.combine(day, time(7, 15), UTC)
        kind = "buy" if quantity > 0 else "sell"
        payment = -amount if quantity > 0 else amount
        events.append(
            Event(moment, kind, ticker, abs(quantity), price, payment, currency, TEXTS[kind])
        )
        fee = -q(amount * FEE, 2)
        after = moment + timedelta(seconds=1)
        events.append(
            Event(after, "commission", ticker, None, None, fee, currency, TEXTS["commission"])
        )
    # Payouts go to what the account held on the record day.
    for ticker, rows in DIVIDENDS.items():
        for record, payment_day, per_share in rows:
            held = held_on(ticker, record)
            if held and payment_day <= END:
                currency = SPECS[ticker].currency
                gross = Decimal(per_share) * held
                moment = datetime.combine(payment_day, time(9), UTC)
                tax = -q(gross * TAX, 2)
                events.append(
                    Event(
                        moment, "dividend", ticker, None, None, gross, currency, TEXTS["dividend"]
                    )
                )
                after = moment + timedelta(seconds=1)
                events.append(
                    Event(after, "tax", ticker, None, None, tax, currency, TEXTS["dividend_tax"])
                )
    for ticker, coupons in COUPONS.items():
        for day, amount in coupons:
            held = held_on(ticker, day)
            if held and amount is not None and START <= day <= END:
                currency = SPECS[ticker].currency
                gross = amount * held
                moment = datetime.combine(day, time(9), UTC)
                tax = -q(gross * TAX, 2)
                events.append(
                    Event(moment, "coupon", ticker, None, None, gross, currency, TEXTS["coupon"])
                )
                after = moment + timedelta(seconds=1)
                events.append(
                    Event(after, "tax", ticker, None, None, tax, currency, TEXTS["coupon_tax"])
                )
    events.sort(key=lambda e: e.moment)  # stable: the order above breaks ties
    return events


@dataclass
class Book:
    """What an account holds while its events play."""

    held: defaultdict[str, int]
    cost: defaultdict[str, Decimal]  # of the held units, in their price currency
    cash: defaultdict[str, Decimal]  # money by ISO code
    average: defaultdict[str, Decimal]  # rubles a unit of foreign money cost


def play(account: str, events: list[Event]) -> tuple[list[dict[str, Any]], Book]:
    book = Book(defaultdict(int), defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal))
    operations = []
    for n, e in enumerate(events, start=1):
        book.cash[e.currency] += e.payment
        if e.kind in {"buy", "sell"}:
            assert e.ticker is not None and e.quantity is not None and e.price is not None
            item = SPECS[e.ticker]
            signed = e.quantity if e.kind == "buy" else -e.quantity
            if item.kind == "currency":  # foreign money: a balance with its average rate
                code = CURRENCY_OF[e.ticker]
                before = book.cash[code]
                if signed > 0:
                    book.average[code] = (book.average[code] * before + e.price * signed) / (
                        before + signed
                    )
                book.cash[code] += signed
            else:
                before_units = book.held[e.ticker]
                book.held[e.ticker] += signed
                if signed > 0:
                    book.cost[e.ticker] += e.price * signed
                else:  # a sale keeps the average price
                    book.cost[e.ticker] = book.cost[e.ticker] * book.held[e.ticker] / before_units
        for code, balance in book.cash.items():
            assert balance >= 0, (account, e.moment, code, balance)
        operations.append(
            {
                "id": f"{account}-{n:04d}",
                "kind": e.kind,
                "date": e.moment,
                "instrument_uid": uid("instrument", e.ticker) if e.ticker else None,
                "payment": money(e.payment, e.currency),
                "quantity": str(e.quantity) if e.quantity else None,
                "price": money(e.price, e.currency) if e.price else None,
                "description": e.text,
            }
        )
    return operations, book


def portfolio(account: str, book: Book, bars: dict[str, list[Bar]]) -> dict[str, Any]:
    def rate(currency: str) -> Decimal:
        return Decimal(1) if currency == "RUB" else close_on(bars[TICKER_OF[currency]], END)

    positions = []
    by_type: defaultdict[str, Decimal] = defaultdict(Decimal)
    gains, basis = Decimal(0), Decimal(0)
    holdings: list[tuple[str, Decimal]] = [(t, Decimal(n)) for t, n in book.held.items() if n]
    holdings += [
        (TICKER_OF[code], balance)
        for code, balance in book.cash.items()
        if code != "RUB" and balance
    ]
    for ticker, quantity in sorted(holdings):
        item = SPECS[ticker]
        if item.kind == "currency":
            currency, average = "RUB", q(book.average[CURRENCY_OF[ticker]], 4)
        else:
            currency, average = item.currency, q(book.cost[ticker] / quantity, 4)
        current = unit_price(ticker, END, bars)
        gain = q((current - average) * quantity, 2)
        nkd = accrued(ticker, END) if item.kind == "bond" else None
        value = (current + (nkd or 0)) * quantity * rate(currency)
        by_type[item.kind] += value
        gains += gain * rate(currency)
        basis += average * quantity * rate(currency)
        positions.append(
            {
                "instrument_uid": uid("instrument", ticker),
                "figi": item.figi,
                "instrument_type": item.kind,
                "quantity": s(quantity),
                "average_price": money(average, currency),
                "current_price": money(current, currency),
                "expected_yield": money(gain, currency),
                "accrued_interest": money(nkd, currency) if nkd is not None else None,
                "blocked": False,
            }
        )
    rubles = book.cash["RUB"]
    positions.append(
        {
            "instrument_uid": uid("instrument", "RUB000UTSTOM"),
            "figi": "RUB000UTSTOM",
            "instrument_type": "currency",
            "quantity": s(rubles),
            "average_price": money(Decimal(1)),
            "current_price": money(Decimal(1)),
            "expected_yield": money(Decimal(0)),
            "accrued_interest": None,
            "blocked": False,
        }
    )
    by_type["currency"] += rubles
    totals = {kind: q(value, 2) for kind, value in sorted(by_type.items())}
    return {
        "account_id": account,
        "total": money(sum(totals.values(), Decimal(0))),
        "total_by_type": {kind: money(value) for kind, value in totals.items()},
        "expected_yield": money(q(gains, 2)),
        "expected_yield_pct": s(q(gains / basis * 100, 2)),
        "positions": positions,
    }


def accounts(bars: dict[str, list[Bar]]) -> None:
    for account, plan in ACCOUNTS.items():
        operations, book = play(account, account_events(plan, bars))
        dump(
            TINVEST / "operations" / f"{account}.yaml",
            operations,
            f"TOperation (§8.2) счёта {account}: сделки, выплаты, налоги и комиссии за два года.",
        )
        found = portfolio(account, book, bars)
        dump(
            TINVEST / "portfolios" / f"{account}.yaml",
            found,
            f"TPortfolio (§8.2) счёта {account} на {END:%d.%m.%Y}: позиции из "
            f"operations/{account}.yaml, цены из свечей.",
        )
        say(f"{account}: total {found['total']['amount']}, {len(operations)} operations")
    dump(
        TINVEST / "accounts.yaml",
        [
            {
                "id": "2000000001",
                "name": "Брокерский счёт",
                "type": "broker",
                "status": "open",
                "opened_date": date(2021, 3, 15),
                "access_level": "read_only",
            },
            {
                "id": "2000000002",
                "name": "ИИС",
                "type": "iis",
                "status": "open",
                "opened_date": date(2023, 1, 20),
                "access_level": "read_only",
            },
        ],
        "TAccount (§8.2): брокерский счёт и ИИС демо-пользователя, оба только для чтения.",
    )


# Reference data

# fmt: off
# ticker: shares, pe, pb, ev/ebitda, nd/ebitda, roe, revenue, net income, ebitda, fcf, debt,
# beta, dividends of 12 months a share.
FUNDAMENTALS: dict[str, tuple[Any, ...]] = {
    "SBER": (21_586_948_000, "4.3", "0.95", None, None, "22.5", "4100000000000", "1600000000000", None, None, None, "1.1", "37.50"),  # noqa: E501
    "GAZP": (23_673_512_900, "3.1", "0.25", "3.8", "2.1", "7.8", "10700000000000", "1200000000000", "2900000000000", "300000000000", "6900000000000", "0.9", "0"),  # noqa: E501
    "LKOH": (692_865_762, "5.2", "0.75", "2.4", "-0.2", "16.5", "8600000000000", "850000000000", "1900000000000", "800000000000", "550000000000", "0.8", "911"),  # noqa: E501
    "YDEX": (390_000_000, "18.5", "4.2", "7.5", "0.3", "28", "1250000000000", "100000000000", "270000000000", "60000000000", "200000000000", "1.2", "110"),  # noqa: E501
    "GMKN": (15_286_339_700, "9.5", "3.1", "5.4", "1.6", "31", "2400000000000", "390000000000", "960000000000", "180000000000", "1100000000000", "0.9", "4.80"),  # noqa: E501
    "ROSN": (10_598_177_817, "5.1", "0.62", "3.6", "1.9", "13.2", "9900000000000", "1000000000000", "2600000000000", "650000000000", "5100000000000", "0.9", "31.68"),  # noqa: E501
    "NVTK": (3_036_306_000, "6.8", "1.0", "6.2", "0.4", "15.4", "1600000000000", "450000000000", "720000000000", "210000000000", "300000000000", "0.9", "83.60"),  # noqa: E501
    "TATN": (2_178_690_700, "5.9", "1.1", "3.9", "-0.3", "19.6", "1900000000000", "240000000000", "380000000000", "190000000000", "40000000000", "0.8", "94.10"),  # noqa: E501
    "MGNT": (101_911_355, "8.2", "1.9", "4.1", "1.5", "18.7", "3100000000000", "75000000000", "240000000000", "60000000000", "450000000000", "0.8", "412"),  # noqa: E501
    "MTSS": (1_998_381_575, "7.4", None, "4.3", "2.2", None, "720000000000", "68000000000", "270000000000", "40000000000", "600000000000", "0.7", "35"),  # noqa: E501
    "PLZL": (1_361_000_000, "8.0", "6.5", "6.8", "0.9", "62", "720000000000", "290000000000", "490000000000", "200000000000", "380000000000", "0.5", "146.86"),  # noqa: E501
    "CHMF": (837_718_660, "6.1", "1.9", "3.7", "-0.1", "27", "800000000000", "180000000000", "260000000000", "100000000000", "120000000000", "0.9", "31.20"),  # noqa: E501
    "NLMK": (5_993_227_240, "6.9", "1.2", "3.9", "0.1", "17", "1000000000000", "150000000000", "280000000000", "90000000000", "140000000000", "0.9", "7.20"),  # noqa: E501
    "ALRS": (7_364_965_630, "9.8", "1.0", "5.5", "0.6", "9.5", "300000000000", "52000000000", "120000000000", "30000000000", "90000000000", "0.8", "3.10"),  # noqa: E501
    "MOEX": (2_276_401_458, "5.4", "1.6", None, None, "29", "130000000000", "90000000000", None, None, None, "0.8", "23.40"),  # noqa: E501
    "VTBR": (5_369_933_029, "2.6", "0.38", None, None, "15", "1900000000000", "520000000000", None, None, None, "1.2", "25.58"),  # noqa: E501
    "AFLT": (3_975_771_215, "5.5", "1.8", "3.3", "2.4", "38", "870000000000", "57000000000", "240000000000", "45000000000", "560000000000", "1.1", "4.10"),  # noqa: E501
    "PHOR": (129_500_000, "9.1", "4.6", "6.0", "1.1", "48", "560000000000", "90000000000", "190000000000", "70000000000", "220000000000", "0.6", "495"),  # noqa: E501
}
# ticker: (consensus, target / price, [(analysts, view, target / price, day)]).
FORECASTS: dict[str, tuple[str, str, list[tuple[str, str, str, date]]]] = {
    "SBER": ("buy", "1.25", [("Аналитики А", "buy", "1.30", date(2026, 8, 28)), ("Аналитики Б", "buy", "1.22", date(2026, 9, 10)), ("Аналитики В", "hold", "1.05", date(2026, 7, 15))]),  # noqa: E501
    "GAZP": ("hold", "1.08", [("Аналитики А", "hold", "1.10", date(2026, 9, 2)), ("Аналитики Б", "sell", "0.92", date(2026, 8, 12))]),  # noqa: E501
    "LKOH": ("buy", "1.20", [("Аналитики А", "buy", "1.25", date(2026, 9, 18)), ("Аналитики В", "buy", "1.15", date(2026, 8, 30))]),  # noqa: E501
    "YDEX": ("buy", "1.35", [("Аналитики Б", "buy", "1.40", date(2026, 9, 25)), ("Аналитики В", "buy", "1.30", date(2026, 9, 1))]),  # noqa: E501
    "GMKN": ("hold", "1.06", [("Аналитики А", "hold", "1.04", date(2026, 9, 8)), ("Аналитики Б", "buy", "1.12", date(2026, 8, 20))]),  # noqa: E501
    "ROSN": ("buy", "1.18", [("Аналитики А", "buy", "1.20", date(2026, 9, 4)), ("Аналитики В", "hold", "1.06", date(2026, 8, 14))]),  # noqa: E501
    "NVTK": ("buy", "1.22", [("Аналитики Б", "buy", "1.25", date(2026, 9, 11)), ("Аналитики В", "buy", "1.18", date(2026, 7, 30))]),  # noqa: E501
    "TATN": ("hold", "1.07", [("Аналитики А", "hold", "1.08", date(2026, 9, 16)), ("Аналитики Б", "hold", "1.05", date(2026, 8, 26))]),  # noqa: E501
    "MGNT": ("buy", "1.28", [("Аналитики А", "buy", "1.30", date(2026, 9, 3)), ("Аналитики В", "buy", "1.24", date(2026, 8, 18))]),  # noqa: E501
    "MTSS": ("hold", "1.04", [("Аналитики Б", "hold", "1.05", date(2026, 9, 9)), ("Аналитики В", "sell", "0.95", date(2026, 7, 21))]),  # noqa: E501
    "PLZL": ("buy", "1.15", [("Аналитики А", "buy", "1.18", date(2026, 9, 22)), ("Аналитики Б", "buy", "1.12", date(2026, 9, 1))]),  # noqa: E501
    "CHMF": ("hold", "1.03", [("Аналитики А", "hold", "1.02", date(2026, 8, 25)), ("Аналитики В", "hold", "1.05", date(2026, 9, 15))]),  # noqa: E501
    "NLMK": ("hold", "1.05", [("Аналитики Б", "hold", "1.06", date(2026, 9, 7)), ("Аналитики В", "hold", "1.03", date(2026, 8, 28))]),  # noqa: E501
    "MOEX": ("buy", "1.24", [("Аналитики А", "buy", "1.26", date(2026, 9, 14)), ("Аналитики Б", "buy", "1.21", date(2026, 8, 31))]),  # noqa: E501
    "PHOR": ("buy", "1.12", [("Аналитики В", "buy", "1.14", date(2026, 9, 19)), ("Аналитики А", "hold", "1.06", date(2026, 8, 7))]),  # noqa: E501
}
REPORTS = [
    ("SBER", date(2026, 7, 29), 2026, 2, "quarter"),
    ("SBER", date(2026, 10, 28), 2026, 3, "quarter"),
    ("SBER", date(2027, 2, 26), 2026, 1, "annual"),
    ("GAZP", date(2026, 8, 28), 2026, 1, "semiannual"),
    ("GAZP", date(2026, 11, 27), 2026, 3, "quarter"),
    ("LKOH", date(2026, 11, 26), 2026, 3, "quarter"),
    ("YDEX", date(2026, 10, 22), 2026, 3, "quarter"),
    ("GMKN", date(2026, 8, 25), 2026, 1, "semiannual"),
    ("GMKN", date(2027, 2, 9), 2026, 1, "annual"),
    ("ROSN", date(2026, 11, 3), 2026, 3, "quarter"),
    ("NVTK", date(2026, 10, 29), 2026, 3, "quarter"),
    ("TATN", date(2026, 11, 12), 2026, 3, "quarter"),
    ("MGNT", date(2026, 10, 27), 2026, 3, "quarter"),
    ("MTSS", date(2026, 11, 18), 2026, 3, "quarter"),
    ("PLZL", date(2026, 8, 20), 2026, 1, "semiannual"),
    ("PLZL", date(2027, 3, 3), 2026, 1, "annual"),
    ("CHMF", date(2026, 10, 23), 2026, 3, "quarter"),
    ("NLMK", date(2026, 10, 21), 2026, 3, "quarter"),
    ("ALRS", date(2026, 11, 10), 2026, 3, "quarter"),
    ("MOEX", date(2026, 11, 20), 2026, 3, "quarter"),
    ("VTBR", date(2026, 10, 30), 2026, 3, "quarter"),
    ("AFLT", date(2026, 11, 25), 2026, 3, "quarter"),
    ("PHOR", date(2026, 11, 17), 2026, 3, "quarter"),
]
# fmt: on


def reference(bars: dict[str, list[Bar]]) -> None:
    last = {ticker: close_on(rows, END) for ticker, rows in bars.items()}

    def year_range(ticker: str) -> tuple[str, str]:
        rows = [r for r in bars[ticker] if r["time"].date() > END - timedelta(365)]
        return s(max(r["high"] for r in rows)), s(min(r["low"] for r in rows))

    fundamentals = []
    for ticker, row in FUNDAMENTALS.items():
        shares, pe, pb, ev, nd, roe, revenue, income, ebitda, fcf, debt, beta, paid = row
        high, low = year_range(ticker)
        fundamentals.append(
            {
                "asset_uid": uid("asset", ticker),
                "currency": "RUB",
                "market_cap": s(q(last[ticker] * shares, 0)),
                "pe_ttm": pe,
                "pb_ttm": pb,
                "ev_ebitda": ev,
                "dividend_yield_ttm": s(q(Decimal(paid) / last[ticker] * 100, 2)),
                "net_debt_ebitda": nd,
                "roe": roe,
                "revenue_ttm": revenue,
                "net_income_ttm": income,
                "ebitda_ttm": ebitda,
                "fcf_ttm": fcf,
                "total_debt": debt,
                "beta": beta,
                "high_52w": high,
                "low_52w": low,
            }
        )
    dump(
        TINVEST / "fundamentals.yaml",
        fundamentals,
        "TFundamentals (§8.2) акций: синтетические мультипликаторы, 52 недели из свечей.",
    )

    forecasts = {}
    for ticker, (consensus, factor, targets) in FORECASTS.items():
        price = last[ticker]
        values = [Decimal(t[2]) * price for t in targets]
        forecasts[ticker] = {
            "consensus": {
                "recommendation": consensus,
                "target_avg": money(q(price * Decimal(factor), 2)),
                "target_min": money(q(min(values), 2)),
                "target_max": money(q(max(values), 2)),
                "upside_pct": s(q((Decimal(factor) - 1) * 100, 2)),
            },
            "targets": [
                {
                    "company": who,
                    "recommendation": view,
                    "target": money(q(Decimal(share) * price, 2)),
                    "date": day,
                }
                for who, view, share, day in targets
            ],
        }
    dump(
        TINVEST / "forecasts.yaml",
        forecasts,
        "TForecasts (§8.2) по тикерам: консенсус и цели синтетических аналитиков; у АЛРОСА, "
        "ВТБ и Аэрофлота консенсуса нет.",
    )

    dividends = {}
    for ticker, rows in DIVIDENDS.items():
        dividends[ticker] = []
        for record, payment, amount in rows:
            assert record.weekday() < 5 and payment.weekday() < 5, (ticker, record, payment)
            price = close_on(bars[ticker], min(record, END))
            dividends[ticker].append(
                {
                    "record_date": record,
                    "payment_date": payment,
                    "last_buy_date": record - timedelta(days=1 if record.weekday() else 3),
                    "amount": money(Decimal(amount), SPECS[ticker].currency),
                    "yield_pct": s(q(Decimal(amount) / price * 100, 2)),
                }
            )
    dump(
        TINVEST / "dividends.yaml",
        dividends,
        "TDividend (§8.2) по тикерам; выплаты после 02.10.2026 объявлены, но ещё не прошли.",
    )

    coupons = {}
    for ticker, rows in COUPONS.items():
        currency = SPECS[ticker].currency
        coupons[ticker] = [
            {
                "coupon_date": day,
                "number": number,
                "amount": money(amount, currency) if amount is not None else None,
            }
            for number, (day, amount) in enumerate(rows, start=1)
        ]
    dump(
        TINVEST / "coupons.yaml",
        coupons,
        "TCoupon (§8.2) по тикерам облигаций, номинал 1000 в валюте облигации; у флоатера "
        "ОФЗ 29024 дальний купон ещё не определён.",
    )

    dump(
        TINVEST / "report_schedule.yaml",
        [
            {
                "instrument_uid": uid("instrument", ticker),
                "report_date": day,
                "period_year": year,
                "period_num": number,
                "period_type": kind,
            }
            for ticker, day, year, number, kind in REPORTS
        ],
        "TReportEvent (§8.2): даты отчётности эмитентов.",
    )


# Documents: three made-up PDFs with a text layer, each in the archive of its e-disclosure row.

FONTS = Path(mpl.get_data_path()) / "fonts" / "ttf"
FOOTER = "Синтетический документ для тестов Kōri. Не является отчётностью эмитента."
type Row = tuple[str, str | None, list[int | None]]  # name, code, values (None: a dash)


def thousands(value: int | None) -> str:
    """Russian forms: spaces between thousands, a negative in brackets, a dash for nothing."""
    if value is None:
        return "-"
    text = f"{abs(value):,}".replace(",", " ")
    return f"({text})" if value < 0 else text


def cells(row: Row) -> list[str]:
    """The number cells of a row; a heading (no code, no values) leaves them empty."""
    _, code, values = row
    if code is None and all(value is None for value in values):
        return ["" for _ in values]
    return [thousands(value) for value in values]


class Document:
    """A canvas that numbers its pages and stamps the footer on each."""

    def __init__(self, path: Path, title: str, size: tuple[float, float]) -> None:
        self.path = path
        self.width, self.height = size
        self.buffer = io.BytesIO()
        # invariant: the same input gives the same bytes (no dates or random ids).
        self.canvas = Canvas(self.buffer, pagesize=size, invariant=1)
        self.canvas.setTitle(title)
        self.canvas.setAuthor("Kōri seed (S1-10)")
        self.canvas.setCreator("scripts/generate_seed.py")
        self.pages: list[Callable[[Canvas], None]] = []

    def page(self, draw: Callable[[Canvas], None]) -> None:
        self.pages.append(draw)

    def save(self) -> bytes:
        total = len(self.pages)
        for number, draw in enumerate(self.pages, start=1):
            draw(self.canvas)
            self.canvas.setFont("DejaVu", 7.5)
            self.canvas.drawString(36, 22, FOOTER)
            self.canvas.drawRightString(self.width - 36, 22, f"Стр. {number} из {total}")
            self.canvas.showPage()
        self.canvas.save()
        data = self.buffer.getvalue()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(data)
        return data


def text_lines(c: Canvas, x: float, y: float, lines: Sequence[str], size: float = 9) -> float:
    c.setFont("DejaVu", size)
    for line in lines:
        c.drawString(x, y, line)
        y -= size * 1.45
    return y


def grid(
    c: Canvas,
    x: float,
    y: float,
    widths: Sequence[float],
    rows: Sequence[Sequence[str]],
    *,
    head: int = 1,
    bold: Callable[[int], bool] = lambda _: False,
    size: float = 7.5,
) -> float:
    """A ruled table, top-left at (x, y): the first column on the left, numbers on the right."""
    height = size * 2.2
    right = x + sum(widths)
    for index, row in enumerate(rows):
        top = y - index * height
        c.line(x, top, right, top)
        font = "DejaVu-Bold" if index < head or bold(index) else "DejaVu"
        c.setFont(font, size)
        left = x
        for column, (width, cell) in enumerate(zip(widths, row, strict=True)):
            base = top - height + size * 0.75
            if index < head or column == 0:
                c.drawString(left + 3, base, cell)
            else:
                c.drawRightString(left + width - 3, base, cell)
            left += width
    bottom = y - len(rows) * height
    c.line(x, bottom, right, bottom)
    edge = x
    for width in [0, *widths]:
        edge += width
        c.line(edge, y, edge, bottom)
    return bottom


def total(rows: list[Row], codes: Sequence[str]) -> list[int]:
    found = [values for _, code, values in rows if code in codes]
    return [sum(v[i] or 0 for v in found) for i in range(len(found[0]))]


def ras_document() -> bytes:
    """The annual RAS statements of LUKOIL for 2025 in thousands of rubles, forms 0710001,
    0710002 and 0710005: the codes of §12.3, brackets for negatives, a dash for nothing."""
    assets: list[Row] = [
        ("Нематериальные активы", "1110", [5_210_431, 4_987_120, 4_512_004]),
        ("Основные средства", "1150", [98_431_220, 92_117_405, 87_650_112]),
        ("Финансовые вложения", "1170", [1_642_118_340, 1_598_774_210, 1_512_330_870]),
        ("Отложенные налоговые активы", "1180", [12_004_551, 10_887_420, 9_954_310]),
        ("Прочие внеоборотные активы", "1190", [3_210_004, 2_998_112, 2_701_450]),
    ]
    assets.append(
        ("Итого по разделу I", "1100", total(assets, ["1110", "1150", "1170", "1180", "1190"]))
    )
    current: list[Row] = [
        ("Запасы", "1210", [41_220_118, 38_904_220, 35_112_006]),
        (
            "Налог на добавленную стоимость по приобретенным ценностям",
            "1220",
            [1_004_220, 987_410, 902_115],
        ),
        ("Дебиторская задолженность", "1230", [512_330_118, 487_210_004, 455_102_330]),
        (
            "Финансовые вложения (за исключением денежных эквивалентов)",
            "1240",
            [120_445_210, 98_004_512, 87_330_214],
        ),
        (
            "Денежные средства и денежные эквиваленты",
            "1250",
            [310_220_487, 287_104_330, 245_887_120],
        ),
        ("Прочие оборотные активы", "1260", [2_110_004, 1_987_220, 1_854_330]),
    ]
    current.append(
        (
            "Итого по разделу II",
            "1200",
            total(current, ["1210", "1220", "1230", "1240", "1250", "1260"]),
        )
    )
    balance = [a + b for a, b in zip(assets[-1][2], current[-1][2], strict=True)]

    long_term: list[Row] = [
        ("Заемные средства", "1410", [312_440_118, 298_870_225, 287_114_330]),
        ("Отложенные налоговые обязательства", "1420", [18_220_104, 16_887_410, 15_104_220]),
        ("Прочие обязательства", "1450", [4_110_220, 3_887_104, 3_402_118]),
    ]
    long_term.append(("Итого по разделу IV", "1400", total(long_term, ["1410", "1420", "1450"])))
    short_term: list[Row] = [
        ("Заемные средства", "1510", [98_887_120, 87_104_330, 76_220_118]),
        ("Кредиторская задолженность", "1520", [187_330_220, 176_104_887, 161_220_004]),
        ("Доходы будущих периодов", "1530", [120_004, 98_220, 87_104]),
        ("Оценочные обязательства", "1540", [14_220_118, 13_104_220, 12_330_114]),
    ]
    short_term.append(
        ("Итого по разделу V", "1500", total(short_term, ["1510", "1520", "1530", "1540"]))
    )
    equity: list[Row] = [
        ("Уставный капитал", "1310", [17_312, 17_312, 17_312]),
        ("Собственные акции, выкупленные у акционеров", "1320", [None, None, -1_204_330]),
        ("Добавочный капитал (без переоценки)", "1350", [33_000, 33_000, 33_000]),
        ("Резервный капитал", "1360", [2_597, 2_597, 2_597]),
    ]
    known = total(equity, ["1310", "1320", "1350", "1360"])
    retained = [
        b - k - lt - st
        for b, k, lt, st in zip(balance, known, long_term[-1][2], short_term[-1][2], strict=True)
    ]
    equity.append(("Нераспределенная прибыль (непокрытый убыток)", "1370", retained))
    equity.append(
        ("Итого по разделу III", "1300", total(equity, ["1310", "1320", "1350", "1360", "1370"]))
    )

    income: list[Row] = [
        ("Выручка", "2110", [1_210_334_870, 1_154_220_118]),
        ("Себестоимость продаж", "2120", [-1_040_887_120, -998_110_004]),
    ]
    income.append(("Валовая прибыль (убыток)", "2100", total(income, ["2110", "2120"])))
    income += [
        ("Коммерческие расходы", "2210", [-54_220_118, -51_004_330]),
        ("Управленческие расходы", "2220", [-38_104_220, -35_887_104]),
    ]
    income.append(("Прибыль (убыток) от продаж", "2200", total(income, ["2100", "2210", "2220"])))
    income += [
        ("Доходы от участия в других организациях", "2310", [412_330_118, 387_104_220]),
        ("Проценты к получению", "2320", [48_220_104, 41_887_330]),
        ("Проценты к уплате", "2330", [-22_104_887, -19_887_210]),
        ("Прочие доходы", "2340", [31_220_004, 28_104_331]),
        ("Прочие расходы", "2350", [-45_887_210, -52_104_118]),
    ]
    income.append(
        (
            "Прибыль (убыток) до налогообложения",
            "2300",
            total(income, ["2200", "2310", "2320", "2330", "2340", "2350"]),
        )
    )
    income += [
        ("Налог на прибыль", "2410", [-27_104_330, -24_887_104]),
        ("Прочее", "2460", [-1_204_330, -987_120]),
    ]
    income.append(("Чистая прибыль (убыток)", "2400", total(income, ["2300", "2410", "2460"])))

    flows: list[Row] = [
        ("Денежные потоки от текущих операций", None, [None, None]),
        ("Поступления, всего", "4110", [1_402_330_118, 1_341_104_220]),
        ("Платежи, всего", "4120", [-1_187_220_330, -1_140_887_104]),
    ]
    flows.append(
        ("Сальдо денежных потоков от текущих операций", "4100", total(flows, ["4110", "4120"]))
    )
    flows += [
        ("Денежные потоки от инвестиционных операций", None, [None, None]),
        ("Поступления, всего", "4210", [498_330_220, 470_104_887]),
        ("Платежи, всего", "4220", [-232_104_118, -219_887_330]),
        (
            "в т.ч. на приобретение, создание и модернизацию внеоборотных активов",
            "4221",
            [-21_330_118, -19_104_220],
        ),
    ]
    flows.append(
        (
            "Сальдо денежных потоков от инвестиционных операций",
            "4200",
            total(flows, ["4210", "4220"]),
        )
    )
    flows += [
        ("Денежные потоки от финансовых операций", None, [None, None]),
        ("Поступления, всего", "4310", [112_330_220, 98_887_104]),
        ("Платежи, всего", "4320", [-571_220_118, -508_104_330]),
        (
            "в т.ч. на уплату дивидендов и иных платежей по распределению прибыли",
            "4322",
            [-498_887_220, -451_330_104],
        ),
    ]
    flows.append(
        ("Сальдо денежных потоков от финансовых операций", "4300", total(flows, ["4310", "4320"]))
    )
    period = total(flows, ["4100", "4200", "4300"])
    flows.append(("Сальдо денежных потоков за отчетный период", "4400", period))
    cash = dict((code, values) for _, code, values in current)["1250"]
    opening, closing = [cash[1], cash[2]], [cash[0], cash[1]]
    rates = [c - o - p for c, o, p in zip(closing, opening, period, strict=True)]
    flows += [
        ("Остаток денежных средств и эквивалентов на начало отчетного периода", "4450", opening),
        ("Остаток денежных средств и эквивалентов на конец отчетного периода", "4500", closing),
        ("Величина влияния изменений курса иностранной валюты по отношению к рублю", "4490", rates),
    ]

    header = [
        "Организация: Публичное акционерное общество «Нефтяная компания «ЛУКОЙЛ»",
        "Идентификационный номер налогоплательщика: 7708004767",
        "Вид экономической деятельности: оптовая торговля сырой нефтью",
        "Единица измерения: в тыс. рублей (по ОКЕИ 384)",
    ]
    doc = Document(
        SEED / "docs" / "lkoh_ras_2025.pdf", "Бухгалтерская отчетность ПАО «ЛУКОЙЛ» за 2025 год", A4
    )
    widths3 = [280, 34, 78, 78, 78]
    head3 = ["Наименование показателя", "Код", "На 31.12.2025", "На 31.12.2024", "На 31.12.2023"]
    widths2 = [342, 34, 86, 86]
    head2 = ["Наименование показателя", "Код", "За 2025 г.", "За 2024 г."]

    def table(rows: list[Row]) -> list[list[str]]:
        return [[row[0], row[1] or "", *cells(row)] for row in rows]

    def sums(rows: list[Row]) -> Callable[[int], bool]:
        totals = {
            "1100",
            "1200",
            "1600",
            "1300",
            "1400",
            "1500",
            "1700",
            "2100",
            "2200",
            "2300",
            "2400",
            "4100",
            "4200",
            "4300",
            "4400",
        }
        return lambda index: (
            index > 0 and (rows[index - 1][1] in totals or rows[index - 1][1] is None)
        )

    def page_assets(c: Canvas) -> None:
        c.setFont("DejaVu-Bold", 13)
        c.drawCentredString(doc.width / 2, 790, "Бухгалтерский баланс")
        c.setFont("DejaVu", 10)
        c.drawCentredString(doc.width / 2, 774, "на 31 декабря 2025 г.")
        c.drawRightString(doc.width - 36, 812, "Форма по ОКУД 0710001")
        y = text_lines(c, 36, 750, header, 8)
        rows: list[Row] = [
            ("АКТИВ", None, [None, None, None]),
            ("I. ВНЕОБОРОТНЫЕ АКТИВЫ", None, [None, None, None]),
            *assets,
            ("II. ОБОРОТНЫЕ АКТИВЫ", None, [None, None, None]),
            *current,
            ("БАЛАНС", "1600", balance),
        ]
        grid(c, 18, y - 6, widths3, [head3, *table(rows)], bold=sums(rows))

    def page_liabilities(c: Canvas) -> None:
        c.setFont("DejaVu-Bold", 11)
        c.drawString(36, 790, "Бухгалтерский баланс на 31 декабря 2025 г. (продолжение)")
        rows: list[Row] = [
            ("ПАССИВ", None, [None, None, None]),
            ("III. КАПИТАЛ И РЕЗЕРВЫ", None, [None, None, None]),
            *equity,
            ("IV. ДОЛГОСРОЧНЫЕ ОБЯЗАТЕЛЬСТВА", None, [None, None, None]),
            *long_term,
            ("V. КРАТКОСРОЧНЫЕ ОБЯЗАТЕЛЬСТВА", None, [None, None, None]),
            *short_term,
            ("БАЛАНС", "1700", balance),
        ]
        grid(c, 18, 770, widths3, [head3, *table(rows)], bold=sums(rows))

    def page_income(c: Canvas) -> None:
        c.setFont("DejaVu-Bold", 13)
        c.drawCentredString(doc.width / 2, 790, "Отчет о финансовых результатах")
        c.setFont("DejaVu", 10)
        c.drawCentredString(doc.width / 2, 774, "за 2025 г.")
        c.drawRightString(doc.width - 36, 812, "Форма по ОКУД 0710002")
        y = text_lines(c, 36, 750, header, 8)
        grid(c, 18, y - 6, widths2, [head2, *table(income)], bold=sums(income))

    def page_flows(c: Canvas) -> None:
        c.setFont("DejaVu-Bold", 13)
        c.drawCentredString(doc.width / 2, 790, "Отчет о движении денежных средств")
        c.setFont("DejaVu", 10)
        c.drawCentredString(doc.width / 2, 774, "за 2025 г.")
        c.drawRightString(doc.width - 36, 812, "Форма по ОКУД 0710005")
        grid(c, 18, 750, widths2, [head2, *table(flows)], bold=sums(flows))

    for draw in (page_assets, page_liabilities, page_income, page_flows):
        doc.page(draw)
    say(f"РСБУ: баланс {balance[0]}, чистая прибыль {income[-1][2][0]}, курс {rates}")
    return doc.save()


def ifrs_document() -> bytes:
    """An IFRS excerpt of LUKOIL for 2025 in millions of rubles: financial position, profit
    or loss with depreciation on its own line, cash flows."""
    current: list[Row] = [
        ("Денежные средства и их эквиваленты", None, [612_330, 587_104]),
        ("Краткосрочные финансовые вложения", None, [48_220, 41_887]),
        ("Дебиторская задолженность, нетто", None, [604_118, 571_330]),
        ("Запасы", None, [498_887, 471_204]),
        ("Предоплата по налогам и прочие оборотные активы", None, [212_330, 198_104]),
    ]
    noncurrent: list[Row] = [
        ("Основные средства", None, [4_120_887, 3_887_330]),
        (
            "Инвестиции в ассоциированные компании и совместные предприятия",
            None,
            [318_104, 297_887],
        ),
        ("Активы в форме права пользования", None, [187_220, 176_104]),
        ("Нематериальные активы", None, [52_330, 48_887]),
        ("Прочие внеоборотные активы", None, [168_104, 152_330]),
    ]

    def add(rows: list[Row]) -> list[int]:
        return [sum(v[i] or 0 for _, _, v in rows) for i in range(2)]

    total_current, total_noncurrent = add(current), add(noncurrent)
    assets = [a + b for a, b in zip(total_current, total_noncurrent, strict=True)]
    short: list[Row] = [
        ("Кредиторская задолженность", None, [701_330, 668_104]),
        (
            "Краткосрочные кредиты и займы и текущая часть долгосрочной задолженности",
            None,
            [98_220, 87_330],
        ),
        ("Краткосрочные обязательства по аренде", None, [41_887, 38_104]),
        ("Налоги к уплате", None, [187_104, 172_330]),
        ("Прочие краткосрочные обязательства", None, [98_330, 91_887]),
    ]
    long: list[Row] = [
        ("Долгосрочные кредиты и займы", None, [287_104, 312_887]),
        ("Долгосрочные обязательства по аренде", None, [158_330, 151_104]),
        ("Отложенные налоговые обязательства", None, [298_887, 276_330]),
        ("Прочие долгосрочные обязательства", None, [112_330, 104_887]),
    ]
    total_short, total_long = add(short), add(long)
    minority = [12_330, 11_887]
    known: list[Row] = [
        ("Уставный капитал", None, [15, 15]),
        ("Собственные акции, выкупленные у акционеров", None, [-412_330, -387_104]),
        ("Прочие резервы", None, [98_104, 87_330]),
    ]
    retained = [
        a - s_ - lg - m - k
        for a, s_, lg, m, k in zip(
            assets, total_short, total_long, minority, add(known), strict=True
        )
    ]
    equity: list[Row] = [*known[:2], ("Нераспределенная прибыль", None, retained), known[2]]
    parent = add(equity)
    total_equity = [p + m for p, m in zip(parent, minority, strict=True)]

    costs: list[Row] = [
        ("Операционные расходы", None, [-598_330, -561_887]),
        (
            "Стоимость приобретенных нефти, газа и продуктов их переработки",
            None,
            [-4_812_104, -4_887_330],
        ),
        ("Транспортные расходы", None, [-312_887, -298_104]),
        ("Коммерческие, общехозяйственные и административные расходы", None, [-287_330, -271_104]),
        ("Износ, истощение и амортизация", None, [-487_104, -452_330]),
        ("Налоги (кроме налога на прибыль)", None, [-1_098_330, -1_120_887]),
        ("Акцизы и экспортные пошлины", None, [-187_104, -198_330]),
    ]
    revenue = [8_598_330, 8_620_104]
    total_costs = add(costs)
    operating = [r + c for r, c in zip(revenue, total_costs, strict=True)]
    finance: list[Row] = [
        ("Финансовые доходы", None, [98_104, 87_330]),
        ("Финансовые расходы", None, [-48_330, -52_887]),
        (
            "Доля в прибыли ассоциированных компаний и совместных предприятий",
            None,
            [41_887, 38_104],
        ),
        ("Курсовые разницы", None, [-12_330, 18_104]),
        ("Прочие расходы", None, [-31_104, -42_330]),
    ]
    before_tax = [o + f for o, f in zip(operating, add(finance), strict=True)]
    tax = [-187_330, -172_104]
    profit = [b + t for b, t in zip(before_tax, tax, strict=True)]
    to_minority = [1_330, 1_104]
    to_parent = [p - m for p, m in zip(profit, to_minority, strict=True)]

    operations: list[Row] = [
        ("Прибыль за год", None, profit),
        ("Износ, истощение и амортизация", None, [487_104, 452_330]),
        ("Расход по налогу на прибыль", None, [-t for t in tax]),
        ("Прочие неденежные статьи", None, [100_300, 94_887]),
        ("Изменения в оборотном капитале", None, [-31_104, -12_330]),
        ("Налог на прибыль уплаченный", None, [-176_330, -168_104]),
    ]
    investing: list[Row] = [
        ("Капитальные затраты", None, [-612_887, -587_330]),
        ("Поступления от реализации основных средств", None, [12_104, 9_887]),
        ("Приобретение финансовых вложений", None, [-48_330, -41_104]),
        ("Поступления от реализации финансовых вложений", None, [31_887, 28_330]),
    ]
    financing: list[Row] = [
        ("Поступления от кредитов и займов", None, [87_104, 98_330]),
        ("Погашение кредитов и займов", None, [-128_330, -112_887]),
        ("Платежи по обязательствам по аренде", None, [-48_104, -45_330]),
        ("Дивиденды, выплаченные акционерам ПАО «ЛУКОЙЛ»", None, [-487_330, -498_104]),
        ("Выкуп собственных акций", None, [-25_226, -24_887]),
    ]
    cfo, cfi, cff = add(operations), add(investing), add(financing)
    opening, closing = [587_104, 512_330], [612_330, 587_104]
    fx = [c - o - a - b - d for c, o, a, b, d in zip(closing, opening, cfo, cfi, cff, strict=True)]

    def rows(*groups: tuple[str, list[Row], str, list[int]]) -> list[Row]:
        out: list[Row] = []
        for title, items, sum_name, sum_values in groups:
            out.append((title, None, [None, None]))
            out += items
            out.append((sum_name, "=", sum_values))
        return out

    position = rows(
        ("Оборотные активы", current, "Итого оборотные активы", total_current),
        ("Внеоборотные активы", noncurrent, "Итого внеоборотные активы", total_noncurrent),
    )
    position.append(("Итого активы", "=", assets))
    position += rows(
        ("Краткосрочные обязательства", short, "Итого краткосрочные обязательства", total_short),
        ("Долгосрочные обязательства", long, "Итого долгосрочные обязательства", total_long),
        ("Капитал", equity, "Итого капитал, относящийся к акционерам ПАО «ЛУКОЙЛ»", parent),
    )
    position += [
        ("Неконтролирующие доли", None, minority),
        ("Итого капитал", "=", total_equity),
        ("Итого обязательства и капитал", "=", [a for a in assets]),
    ]
    results: list[Row] = [
        ("Выручка от реализации (включая акцизы и экспортные пошлины)", "=", revenue)
    ]
    results += [("Затраты и прочие расходы", None, [None, None]), *costs]
    results += [
        ("Итого затраты и прочие расходы", "=", total_costs),
        ("Прибыль от операционной деятельности", "=", operating),
        *finance,
        ("Прибыль до налога на прибыль", "=", before_tax),
        ("Текущий и отложенный налог на прибыль", None, tax),
        ("Прибыль за год", "=", profit),
        ("Прибыль за год, относящаяся к акционерам ПАО «ЛУКОЙЛ»", None, to_parent),
        ("Прибыль за год, относящаяся к неконтролирующим долям", None, to_minority),
    ]
    cash = rows(
        (
            "Операционная деятельность",
            operations,
            "Чистые денежные средства, полученные от операционной деятельности",
            cfo,
        ),
        (
            "Инвестиционная деятельность",
            investing,
            "Чистые денежные средства, использованные в инвестиционной деятельности",
            cfi,
        ),
        (
            "Финансовая деятельность",
            financing,
            "Чистые денежные средства, использованные в финансовой деятельности",
            cff,
        ),
    )
    cash += [
        ("Влияние изменения курсов валют на денежные средства и их эквиваленты", None, fx),
        ("Денежные средства и их эквиваленты на начало года", None, opening),
        ("Денежные средства и их эквиваленты на конец года", "=", closing),
    ]

    doc = Document(
        SEED / "docs" / "lkoh_ifrs_2025.pdf",
        "Консолидированная финансовая отчетность ПАО «ЛУКОЙЛ» по МСФО за 2025 год (выдержка)",
        A4,
    )
    widths = [356, 100, 100]

    def table(found: list[Row], head: list[str]) -> list[list[str]]:
        return [head] + [[row[0], *cells(row)] for row in found]

    def strong(found: list[Row]) -> Callable[[int], bool]:
        # Sums and the headings of the sections.
        return lambda index: (
            index > 0 and (found[index - 1][1] == "=" or not any(cells(found[index - 1])))
        )

    def cover(c: Canvas) -> None:
        c.setFont("DejaVu-Bold", 18)
        c.drawCentredString(doc.width / 2, 640, "ПАО «ЛУКОЙЛ»")
        c.setFont("DejaVu", 13)
        y = 600
        for line in (
            "Консолидированная финансовая отчетность",
            "по Международным стандартам финансовой отчетности",
            "за год, закончившийся 31 декабря 2025 года",
        ):
            c.drawCentredString(doc.width / 2, y, line)
            y -= 20
        y = text_lines(c, 72, 470, ["Выдержка. Содержание:"], 10)
        text_lines(
            c,
            90,
            y,
            [
                "Консолидированный отчет о финансовом положении ........ 2",
                "Консолидированный отчет о прибылях и убытках ........ 3",
                "Консолидированный отчет о движении денежных средств ........ 4",
                "Суммы в миллионах российских рублей, если не указано иное.",
            ],
            10,
        )

    def page(title: str, found: list[Row], head: list[str]) -> Callable[[Canvas], None]:
        def draw(c: Canvas) -> None:
            c.setFont("DejaVu-Bold", 12)
            c.drawString(36, 790, title)
            c.setFont("DejaVu", 8)
            c.drawString(36, 776, "ПАО «ЛУКОЙЛ». Млн руб.")
            grid(c, 18, 760, widths, table(found, head), bold=strong(found))

        return draw

    doc.page(cover)
    doc.page(
        page(
            "Консолидированный отчет о финансовом положении",
            position,
            ["", "31 декабря 2025 г.", "31 декабря 2024 г."],
        )
    )
    doc.page(
        page("Консолидированный отчет о прибылях и убытках", results, ["", "2025 г.", "2024 г."])
    )
    doc.page(
        page(
            "Консолидированный отчет о движении денежных средств", cash, ["", "2025 г.", "2024 г."]
        )
    )
    say(f"МСФО: активы {assets}, прибыль {profit}, курсовые {fx}")
    return doc.save()


def presentation() -> bytes:
    """The transformation strategy of Magnit as five landscape slides with a bar chart."""
    size = landscape(A4)
    doc = Document(
        SEED / "docs" / "mgnt_strategy_presentation.pdf",
        "Презентация о стратегии трансформации ПАО «Магнит»",
        size,
    )
    w, h = size

    def title(c: Canvas, text: str) -> None:
        c.setFillColorRGB(0.89, 0.02, 0.07)
        c.rect(0, h - 70, w, 70, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("DejaVu-Bold", 24)
        c.drawString(40, h - 48, text)
        c.setFillColorRGB(0, 0, 0)

    def cover(c: Canvas) -> None:
        c.setFillColorRGB(0.89, 0.02, 0.07)
        c.rect(0, 0, w, h, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("DejaVu-Bold", 40)
        c.drawString(60, h / 2 + 40, "ПАО «Магнит»")
        c.setFont("DejaVu", 24)
        c.drawString(60, h / 2, "Стратегия трансформации")
        c.setFont("DejaVu", 14)
        c.drawString(60, h / 2 - 34, "Презентация для инвесторов, октябрь 2018 года")
        c.setFillColorRGB(0, 0, 0)

    def figures(c: Canvas) -> None:
        title(c, "Ключевые показатели 2017 года")
        tiles = [
            ("Магазинов", "16 350", ""),
            ("Выручка", "1 143", "млрд руб."),
            ("Рентабельность EBITDA", "7,6%", ""),
            ("Торговая площадь", "6,4", "млн м²"),
        ]
        for index, (label, value, unit) in enumerate(tiles):
            x = 40 + index * 195
            c.setStrokeColorRGB(0.6, 0.6, 0.6)
            c.rect(x, h - 270, 180, 150, stroke=1, fill=0)
            c.setFont("DejaVu", 12)
            c.drawString(x + 14, h - 150, label)
            c.setFont("DejaVu-Bold", 20)
            c.drawString(x + 14, h - 200, value)
            c.setFont("DejaVu", 12)
            c.drawString(x + 14, h - 224, unit)
        text_lines(
            c,
            40,
            h - 320,
            [
                "Сеть растёт во всех форматах: магазины у дома, супермаркеты и аптеки.",
                "Число покупателей в 2017 году превысило 3,8 млрд чеков.",
            ],
            13,
        )

    def revenue(c: Canvas) -> None:
        title(c, "Выручка, млрд руб.")
        years = [("2014", 764), ("2015", 950), ("2016", 1075), ("2017", 1143), ("2018П", 1237)]
        base, top = 110, h - 130
        scale = (top - base) / 1300
        for index, (year, value) in enumerate(years):
            x = 90 + index * 140
            c.setFillColorRGB(0.89, 0.02, 0.07)
            c.rect(x, base, 80, value * scale, stroke=0, fill=1)
            c.setFillColorRGB(0, 0, 0)
            c.setFont("DejaVu-Bold", 14)
            c.drawCentredString(x + 40, base + value * scale + 8, f"{value:,}".replace(",", " "))
            c.setFont("DejaVu", 12)
            c.drawCentredString(x + 40, base - 18, year)
        c.setFont("DejaVu", 11)
        c.drawString(40, 70, "Среднегодовой рост выручки 2014-2018 годов: 12,8%.")

    def priorities(c: Canvas) -> None:
        title(c, "Приоритеты трансформации")
        text_lines(
            c,
            60,
            h - 130,
            [
                "1. Обновление форматов магазинов и редизайн 3 000 магазинов в год",
                "2. Рост доли собственных торговых марок в продажах",
                "3. Цифровые сервисы и программа лояльности",
                "4. Оптимизация логистики и складской сети",
                "5. Снижение операционных издержек на квадратный метр",
            ],
            16,
        )

    def targets(c: Canvas) -> None:
        title(c, "Целевые ориентиры до 2023 года")
        rows = [
            ["Показатель", "2018", "Цель 2023"],
            ["Рентабельность EBITDA", "7,1%", "8% и выше"],
            ["Доля СТМ в продажах", "12%", "20% и выше"],
            ["Капитальные затраты, млрд руб. в год", "60", "45-50"],
            ["Чистый долг / EBITDA", "1,2x", "не выше 1,5x"],
        ]
        grid(c, 60, h - 120, [380, 150, 180], rows, size=13)

    for draw in (cover, figures, revenue, priorities, targets):
        doc.page(draw)
    return doc.save()


def archive(row_file_id: int, outer: str, inner: str, data: bytes, day: date) -> None:
    folder = SEED / "edisclosure" / "archives" / str(row_file_id)
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.iterdir():
        old.unlink()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo(inner, date_time=(day.year, day.month, day.day, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, data)  # a Cyrillic name gets the UTF-8 flag
    (folder / outer).write_bytes(out.getvalue())


def documents() -> None:
    pdfmetrics.registerFont(TTFont("DejaVu", str(FONTS / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(FONTS / "DejaVuSans-Bold.ttf")))
    # The rows of seed/edisclosure/files these documents belong to (S1-12 snapshots).
    archive(
        1915678,
        "RSBU_2025.pdf.zip",
        "Бухгалтерская отчетность ПАО ЛУКОЙЛ за 2025 год.pdf",
        ras_document(),
        date(2026, 3, 20),
    )
    archive(
        1915683,
        "MSFO_2025.pdf.zip",
        "Консолидированная финансовая отчетность МСФО за 2025 год.pdf",
        ifrs_document(),
        date(2026, 3, 20),
    )
    archive(
        1469220,
        "Presentation.pdf.zip",
        "Презентация о стратегии трансформации.pdf",
        presentation(),
        date(2018, 10, 5),
    )


def main() -> None:
    bars = candles()
    write_candles(bars)
    dump(
        TINVEST / "instruments.yaml",
        instruments(),
        f"TInstrument (§8.2): синтетический справочник из {len(SPECS)} инструментов. "
        "Свечи лежат в candles/<ticker>.csv.",
    )
    accounts(bars)
    reference(bars)
    documents()
    say({t: s(close_on(rows, END)) for t, rows in bars.items()}.__repr__())


if __name__ == "__main__":
    main()
