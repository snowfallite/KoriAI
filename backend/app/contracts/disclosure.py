"""DTOs of the disclosure port, e-disclosure.ru (tech.md §8.5)."""

from datetime import date

from app.contracts.common import Contract, FileSection, Sha256, UtcDatetime


class DisclosureCompanyHit(Contract):
    """An item of foundCompaniesList in a search answer; the card confirms INN and OGRN."""

    company_id: int
    name: str
    region: str | None
    branch: str | None
    last_activity: UtcDatetime | None
    doc_count: int | None


class DisclosureCompany(Contract):
    """The «Общие сведения» block of a card; a foreign issuer has no INN or OGRN."""

    company_id: int
    full_name: str
    short_name: str
    inn: str | None
    ogrn: str | None
    address: str | None
    page_url: str


class DisclosureFileRow(Contract):
    """A row of table.files-table."""

    file_id: int
    section: FileSection
    doc_type_raw: str
    period_raw: str  # '2025', '2026, 6 месяцев'; '' in a section without a period column
    description: str | None  # the only mark of presentations and press releases
    basis_date: date | None
    published_date: date
    file_ext: str
    size_raw: str
    page_url: str
    download_url: str


class DownloadedFile(Contract):
    """The adapter writes the bytes to FilesPort right away."""

    file_id: int
    filename: str
    content_type: str
    size: int
    sha256: Sha256
    storage_key: str


class IssuerRef(Contract):
    """A row of backend/fixtures/reference/issuers.csv."""

    ticker: str  # links the row to instruments.ticker and through it to asset_uid
    edisclosure_id: int
    inn: str | None
    ogrn: str | None
    name: str
    short_name: str | None
