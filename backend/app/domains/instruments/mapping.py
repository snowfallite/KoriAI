"""Instruments of T-Invest and of the table as rows and API DTOs (tech.md §5.2, §6.4, §8.2): pure
functions."""

import re

from app.contracts.api.instruments import InstrumentBrief
from app.contracts.tinvest import TInstrument
from app.db.schema.broker import Instrument

# A logo name becomes one segment of a URL path: plain characters only.
LOGO_BASE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
LOGO_ROUTE = "/api/media/logos"
LOGO_CDN = "https://invest-brands.cdn-tinkoff.ru"


def is_logo_base(text: str) -> bool:
    return LOGO_BASE.fullmatch(text) is not None


def logo_base(logo_name: str | None) -> str | None:
    """brand.logo_name of T-Invest without '.png' (§5.2); None for anything but a plain name."""
    base = (logo_name or "").removesuffix(".png")
    return base if is_logo_base(base) else None


def logo_url(base: str | None) -> str | None:
    """The logo through the media proxy (§6.4): the SPA never loads the CDN itself (AD-09)."""
    return f"{LOGO_ROUTE}/{base}" if base is not None and is_logo_base(base) else None


def logo_cdn_url(base: str, size: int) -> str:
    """Where T-Invest keeps the logo in the given size (§8.2)."""
    return f"{LOGO_CDN}/{base}x{size}.png"


def row(item: TInstrument) -> dict[str, object]:
    """The instruments row of a T-Invest instrument."""
    return {
        "uid": item.uid,
        "figi": item.figi,
        "ticker": item.ticker,
        "class_code": item.class_code,
        "isin": item.isin,
        "name": item.name,
        "instrument_type": item.instrument_type,
        "currency": item.currency,
        "lot": item.lot,
        "asset_uid": item.asset_uid,
        "brand_uid": item.brand_uid,
        "logo_base": logo_base(item.logo_name),
        "brand_color": item.brand_color,
        "sector": item.sector,
        "country_iso": item.country_iso,
        "exchange": item.exchange,
        "for_qual_only": item.for_qual_only,
    }


def brief(item: Instrument | TInstrument) -> InstrumentBrief:
    base = item.logo_base if isinstance(item, Instrument) else logo_base(item.logo_name)
    return InstrumentBrief.model_validate(
        {
            "uid": item.uid,
            "ticker": item.ticker,
            "class_code": item.class_code,
            "name": item.name,
            "instrument_type": item.instrument_type,
            "currency": item.currency,
            "logo_url": logo_url(base),
            "brand_color": item.brand_color,
        }
    )
