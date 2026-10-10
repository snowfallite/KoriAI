"""The instrument reference (tech.md §6.4, §8.2, §9.7): instruments come from the table, T-Invest
gives the missing ones and the table keeps them; logos; ruble rates of foreign currencies;
resolving what a user calls an instrument."""

import asyncio
import re
import uuid
from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import structlog
from pydantic import SecretStr

from app.contracts.api.instruments import InstrumentBrief
from app.contracts.tinvest import TInstrument, TInstrumentBrief
from app.core.errors import AppError, PermanentGatewayError
from app.db.base import UnitOfWork
from app.domains.instruments import mapping, repo
from app.gateways.tinvest.port import TInvestPort

log = structlog.get_logger(__name__)

# Currency instruments of the MOEX currency market whose last price is rubles per one unit
# (§6.4). Currencies quoted per 100 units (JPY, KZT and others) would need the nominal, which
# TInstrument does not carry.
FX_TICKERS: dict[str, str] = {
    "USD": "USD000UTSTOM",
    "EUR": "EUR_RUB__TOM",
    "CNY": "CNYRUB_TOM",
    "HKD": "HKDRUB_TOM",
}
FX_CLASS_CODE = "CETS"
CANDIDATES = 5  # instrument_lookup offers up to five (§9.7)
SEARCH_LIMIT = 20
TICKER_CLASSCODE = re.compile(r"(.+)_([A-Z0-9]+)")


@dataclass(frozen=True, slots=True)
class Ambiguous:
    """Several instruments fit: the caller asks the user or picks one (§9.7)."""

    candidates: list[InstrumentBrief]


def logo_source(logo_base: str, size: int) -> str | None:
    """The CDN address of a logo, or None for a name that is no plain logo name."""
    return mapping.logo_cdn_url(logo_base, size) if mapping.is_logo_base(logo_base) else None


def _uuid(text: str) -> UUID | None:
    try:
        return uuid.UUID(text)
    except ValueError:
        return None


def _exact(query: str, hits: Sequence[TInstrumentBrief]) -> list[TInstrumentBrief]:
    """Hits named exactly: TICKER_CLASSCODE, then the ISIN, then the ticker."""
    key = query.upper()
    names: list[Callable[[TInstrumentBrief], str]] = [
        lambda hit: f"{hit.ticker}_{hit.class_code}",
        lambda hit: hit.isin or "",
        lambda hit: hit.ticker,
    ]
    for name in names:
        if found := [hit for hit in hits if name(hit).upper() == key]:
            return found
    return []


class InstrumentsService:
    def __init__(self, uow: UnitOfWork, tinvest: TInvestPort) -> None:
        self._uow = uow
        self._tinvest = tinvest

    async def briefs(self, token: SecretStr, uids: Iterable[UUID]) -> dict[UUID, InstrumentBrief]:
        """Briefs of the instruments; one T-Invest does not know is left out."""
        wanted = list(dict.fromkeys(uids))
        if not wanted:
            return {}
        async with self._uow as session:
            rows = await repo.by_uids(session, wanted)
        found = {row.uid: mapping.brief(row) for row in rows}
        fetched = await self._fetch(token, [uid for uid in wanted if uid not in found])
        return found | {item.uid: mapping.brief(item) for item in fetched}

    async def rub_rates(self, token: SecretStr, currencies: Collection[str]) -> dict[str, Decimal]:
        """Rubles per unit of each currency at the last price of its currency instrument (§6.4);
        a currency without a known instrument or price is left out."""
        uids: dict[str, UUID] = {}
        for currency in sorted(currencies):
            ticker = FX_TICKERS.get(currency)
            uid = await self._uid_of(token, ticker, FX_CLASS_CODE) if ticker else None
            if uid is not None:
                uids[currency] = uid
        if not uids:
            return {}
        prices = await self._tinvest.get_last_prices(token, list(uids.values()))
        last = {price.instrument_uid: price.price for price in prices if price.price > 0}
        return {currency: last[uid] for currency, uid in uids.items() if uid in last}

    async def resolve(self, token: SecretStr, text: str) -> InstrumentBrief | Ambiguous:
        """A ticker, TICKER_CLASSCODE, an ISIN, a uid or a name as one instrument, or the
        candidates when several fit (§9.7)."""
        query = text.strip()
        if not query:
            raise AppError("validation_error", "Назовите инструмент")
        uid = _uuid(query)
        hits = [uid] if uid is not None else [h.uid for h in await self._search(token, query)]
        briefs = await self.briefs(token, hits[:CANDIDATES])
        found = [briefs[uid] for uid in hits[:CANDIDATES] if uid in briefs]
        if not found:
            raise AppError("not_found", f"Инструмент «{query}» не найден")
        return found[0] if len(found) == 1 else Ambiguous(candidates=found)

    async def has_logo(self, logo_base: str) -> bool:
        """Some known instrument wears this logo: the media proxy fetches no other."""
        async with self._uow as session:
            return await repo.has_logo(session, logo_base)

    async def _search(self, token: SecretStr, query: str) -> list[TInstrumentBrief]:
        """The hits of the T-Invest search, narrowed to the exact ones when there are any."""
        hits = await self._tinvest.find_instruments(token, query, SEARCH_LIMIT)
        if exact := _exact(query, hits):
            return exact
        # The search knows tickers, not SBER_TQBR: look for the ticker, keep the class code.
        pair = TICKER_CLASSCODE.fullmatch(query.upper())
        if pair is not None:
            ticker, class_code = pair.groups()
            found = await self._tinvest.find_instruments(token, ticker, SEARCH_LIMIT)
            named = [
                hit
                for hit in found
                if (hit.ticker.upper(), hit.class_code.upper()) == (ticker, class_code)
            ]
            if named:
                return named
        return hits

    async def _uid_of(self, token: SecretStr, ticker: str, class_code: str) -> UUID | None:
        async with self._uow as session:
            row = await repo.by_ticker(session, ticker, class_code)
        if row is not None:
            return row.uid
        hits = await self._tinvest.find_instruments(token, ticker, SEARCH_LIMIT)
        hit = next((h for h in hits if (h.ticker, h.class_code) == (ticker, class_code)), None)
        if hit is None:
            return None
        await self._fetch(token, [hit.uid])  # the table keeps it for the next request
        return hit.uid

    async def _fetch(self, token: SecretStr, uids: Sequence[UUID]) -> list[TInstrument]:
        """Full instruments from T-Invest, added to the table on the way."""
        results = await asyncio.gather(
            *(self._tinvest.get_instrument(token, uid) for uid in uids), return_exceptions=True
        )
        items = []
        for uid, result in zip(uids, results, strict=True):
            if isinstance(result, PermanentGatewayError) and result.code == "not_found":
                log.warning("instrument_unknown", instrument_uid=str(uid))
                continue
            if isinstance(result, BaseException):
                raise result
            items.append(result)
        if items:
            async with self._uow as session:
                await repo.add_missing(session, [mapping.row(item) for item in items])
        return items
