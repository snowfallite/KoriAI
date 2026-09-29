"""Broker, instruments, market data (tech.md §5.2)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.schema.base import Base, Json, Now, UpdatedAt, UuidPk

Price = Numeric(20, 9)
Amount = Numeric(24, 9)


class BrokerConnection(Base):
    __tablename__ = "broker_connections"
    __table_args__ = (
        CheckConstraint("broker in ('tinvest')", name="broker"),
        CheckConstraint("status in ('active','invalid')", name="status"),
        UniqueConstraint("user_id", "broker"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    broker: Mapped[str] = mapped_column(server_default="tinvest")
    token_ciphertext: Mapped[bytes]
    token_nonce: Mapped[bytes]  # 12 bytes of AES-GCM
    token_key_id: Mapped[str]
    token_hint: Mapped[str]  # last 4 characters
    status: Mapped[str] = mapped_column(server_default="active")
    last_verified_at: Mapped[datetime | None]
    last_error_code: Mapped[str | None]
    created_at: Mapped[Now]
    updated_at: Mapped[UpdatedAt]


class BrokerAccount(Base):
    __tablename__ = "broker_accounts"
    __table_args__ = (
        CheckConstraint("alias ~ '^acc[0-9]+$'", name="alias"),
        CheckConstraint("type in ('broker','iis','invest_box','invest_fund','other')", name="type"),
        CheckConstraint("status in ('new','open','closed','other')", name="status"),
        CheckConstraint("access_level in ('read_only')", name="access_level"),
        UniqueConstraint("connection_id", "external_id"),
        UniqueConstraint("connection_id", "alias"),
    )

    id: Mapped[UuidPk]
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("broker_connections.id", ondelete="CASCADE")
    )
    external_id: Mapped[str]  # T-Invest account_id, never sent to the LLM
    alias: Mapped[str]
    name: Mapped[str]
    type: Mapped[str]
    status: Mapped[str]
    opened_at: Mapped[date | None]
    access_level: Mapped[str]
    is_hidden: Mapped[bool] = mapped_column(server_default=text("false"))
    updated_at: Mapped[UpdatedAt]


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        CheckConstraint(
            "instrument_type in "
            "('share','bond','etf','currency','future','option','structured','index','other')",
            name="instrument_type",
        ),
        UniqueConstraint("ticker", "class_code"),
    )

    uid: Mapped[uuid.UUID] = mapped_column(primary_key=True)  # T-Invest instrument_uid
    figi: Mapped[str | None]
    ticker: Mapped[str]
    class_code: Mapped[str]
    isin: Mapped[str | None]
    name: Mapped[str]
    instrument_type: Mapped[str]
    currency: Mapped[str]  # ISO 4217, upper case
    lot: Mapped[int] = mapped_column(server_default=text("1"))
    asset_uid: Mapped[uuid.UUID | None]
    brand_uid: Mapped[uuid.UUID | None]
    logo_base: Mapped[str | None]  # brand.logo_name without '.png'
    brand_color: Mapped[str | None]  # '#RRGGBB'
    sector: Mapped[str | None]
    country_iso: Mapped[str | None]
    exchange: Mapped[str | None]
    for_qual_only: Mapped[bool] = mapped_column(server_default=text("false"))
    updated_at: Mapped[UpdatedAt]


Index("instruments_isin_idx", Instrument.isin)
Index("instruments_figi_idx", Instrument.figi)
Index("instruments_asset_idx", Instrument.asset_uid)
Index(
    "instruments_name_trgm",
    Instrument.name,
    postgresql_using="gin",
    postgresql_ops={"name": "gin_trgm_ops"},
)
Index(
    "instruments_ticker_trgm",
    Instrument.ticker,
    postgresql_using="gin",
    postgresql_ops={"ticker": "gin_trgm_ops"},
)


class CandleDaily(Base):
    __tablename__ = "candles_daily"

    instrument_uid: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instruments.uid", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(primary_key=True)
    open: Mapped[Decimal] = mapped_column(Price)
    high: Mapped[Decimal] = mapped_column(Price)
    low: Mapped[Decimal] = mapped_column(Price)
    close: Mapped[Decimal] = mapped_column(Price)
    volume: Mapped[int] = mapped_column(BigInteger)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(primary_key=True)  # trading day, Europe/Moscow
    total_value: Mapped[Decimal] = mapped_column(Amount)
    currency: Mapped[str]
    expected_yield: Mapped[Decimal | None] = mapped_column(Amount)
    positions: Mapped[list[Json]]  # [{instrument_uid, quantity, value}]
    created_at: Mapped[Now]
