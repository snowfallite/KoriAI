"""Issuers and disclosures (tech.md §5.4)."""

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

from app.db.schema.base import Base, IdentityPk, Now, UpdatedAt, UuidPk

Confidence = Numeric(4, 3)


class Issuer(Base):
    __tablename__ = "issuers"
    __table_args__ = (
        CheckConstraint(
            "resolve_status in ('manual','auto_confirmed','auto_candidate','unresolved')",
            name="resolve_status",
        ),
    )

    id: Mapped[UuidPk]
    name: Mapped[str]  # full name
    short_name: Mapped[str | None]
    inn: Mapped[str | None] = mapped_column(unique=True)
    ogrn: Mapped[str | None] = mapped_column(unique=True)
    edisclosure_id: Mapped[int | None] = mapped_column(unique=True)  # company.aspx?id=
    asset_uid: Mapped[uuid.UUID | None] = mapped_column(unique=True)  # T-Invest asset
    brand_uid: Mapped[uuid.UUID | None]
    resolve_status: Mapped[str] = mapped_column(server_default="unresolved")
    resolve_confidence: Mapped[Decimal | None] = mapped_column(Confidence)
    last_synced_at: Mapped[datetime | None]
    created_at: Mapped[Now]
    updated_at: Mapped[UpdatedAt]


Index(
    "issuers_name_trgm",
    Issuer.name,
    postgresql_using="gin",
    postgresql_ops={"name": "gin_trgm_ops"},
)


class DisclosureDocument(Base):
    __tablename__ = "disclosure_documents"
    __table_args__ = (
        CheckConstraint("source in ('edisclosure')", name="source"),
        CheckConstraint(
            "section in ('charter','annual','ras','ifrs','issuer_reports',"
            "'affiliates','emission','investors','other','meetings')",
            name="section",
        ),
        CheckConstraint(
            "kind in ('ifrs_annual','ifrs_interim','ras_annual','ras_interim',"
            "'annual_report','issuer_report','presentation','press_release','other')",
            name="kind",
        ),
        CheckConstraint("standard in ('ifrs','ras','none')", name="standard"),
        CheckConstraint("period_months in (3,6,9,12)", name="period_months"),
        CheckConstraint(
            "fetch_status in ('listed','downloaded','failed','skipped')", name="fetch_status"
        ),
        CheckConstraint(
            "facts_status in ('none','done','failed','not_applicable')", name="facts_status"
        ),
        CheckConstraint("index_status in ('none','done','failed')", name="index_status"),
        UniqueConstraint("source", "source_file_id"),
    )

    id: Mapped[UuidPk]
    issuer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("issuers.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(server_default="edisclosure")
    source_file_id: Mapped[int] = mapped_column(BigInteger)  # FileLoad.ashx?Fileid=
    section: Mapped[str]
    source_page_url: Mapped[str]  # files.aspx?id=..&type=..
    doc_type_raw: Mapped[str]
    description: Mapped[str | None]  # description line under the row on the site
    kind: Mapped[str]
    standard: Mapped[str]
    period_year: Mapped[int | None]
    period_months: Mapped[int | None]
    period_label: Mapped[str]  # as on the site: '2026, 6 месяцев'; '' without a period column
    basis_date: Mapped[date | None]
    published_date: Mapped[date]
    file_ext: Mapped[str]  # 'zip', 'pdf', 'xlsx', ...
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    fetch_status: Mapped[str] = mapped_column(server_default="listed")
    facts_status: Mapped[str] = mapped_column(server_default="none")
    index_status: Mapped[str] = mapped_column(server_default="none")
    error_code: Mapped[str | None]
    sha256: Mapped[bytes | None]
    storage_key: Mapped[str | None]
    extractor_version: Mapped[int | None]  # parser or extractor version behind the facts
    created_at: Mapped[Now]
    updated_at: Mapped[UpdatedAt]


Index(
    "disclosure_documents_issuer_idx",
    DisclosureDocument.issuer_id,
    DisclosureDocument.kind,
    DisclosureDocument.period_year.desc(),
)
Index(
    "disclosure_documents_pending_idx",
    DisclosureDocument.fetch_status,
    DisclosureDocument.facts_status,
    DisclosureDocument.index_status,
)


class DocumentPart(Base):
    __tablename__ = "document_parts"
    __table_args__ = (UniqueConstraint("document_id", "name"),)

    id: Mapped[UuidPk]
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("disclosure_documents.id", ondelete="CASCADE")
    )
    name: Mapped[str]  # file name inside the archive
    ext: Mapped[str]
    sha256: Mapped[bytes]
    storage_key: Mapped[str]
    pages: Mapped[int | None]
    is_primary: Mapped[bool] = mapped_column(server_default=text("false"))


class FinancialFact(Base):
    __tablename__ = "financial_facts"
    __table_args__ = (
        CheckConstraint("standard in ('ifrs','ras')", name="standard"),
        CheckConstraint("statement in ('income','balance','cashflow')", name="statement"),
        CheckConstraint("period_months in (3,6,9,12)", name="period_months"),
        CheckConstraint("extraction in ('ras_rule','llm','manual')", name="extraction"),
        CheckConstraint("check_status in ('ok','mismatch','unchecked')", name="check_status"),
        # PostgreSQL truncates the default name to 63 characters.
        UniqueConstraint(
            "document_id",
            "statement",
            "metric",
            "period_end",
            "period_months",
            name="financial_facts_document_id_statement_metric_period_end_per_key",
        ),
    )

    id: Mapped[IdentityPk]
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("disclosure_documents.id", ondelete="CASCADE")
    )
    issuer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("issuers.id", ondelete="CASCADE"))
    standard: Mapped[str]
    statement: Mapped[str]
    metric: Mapped[str]  # MetricCode (§12)
    metric_raw: Mapped[str | None]  # line wording in the document
    line_code: Mapped[str | None]  # RAS line code
    period_end: Mapped[date]
    period_months: Mapped[int]
    value: Mapped[Decimal] = mapped_column(Numeric(28, 4))  # currency units, multiplier applied
    currency: Mapped[str]
    is_consolidated: Mapped[bool]
    extraction: Mapped[str]
    confidence: Mapped[Decimal] = mapped_column(Confidence)
    page: Mapped[int | None]
    check_status: Mapped[str] = mapped_column(server_default="unchecked")
    created_at: Mapped[Now]


Index(
    "financial_facts_issuer_idx",
    FinancialFact.issuer_id,
    FinancialFact.metric,
    FinancialFact.period_end.desc(),
)
