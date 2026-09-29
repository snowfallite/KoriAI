"""Instrument DTOs (tech.md §6.4)."""

from uuid import UUID

from app.contracts.common import Contract, Currency, InstrumentType


class InstrumentBrief(Contract):
    uid: UUID
    ticker: str
    class_code: str
    name: str
    instrument_type: InstrumentType
    currency: Currency
    logo_url: str | None  # /api/media/logos/...
    brand_color: str | None


class InstrumentOut(InstrumentBrief):
    isin: str | None
    figi: str | None
    lot: int
    sector: str | None
    country_iso: str | None
    exchange: str | None
