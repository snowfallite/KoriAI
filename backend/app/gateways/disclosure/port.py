"""Disclosure port, e-disclosure.ru (tech.md §8.5)."""

from typing import Protocol

from app.contracts.common import FileSection
from app.contracts.disclosure import (
    DisclosureCompany,
    DisclosureCompanyHit,
    DisclosureFileRow,
    DownloadedFile,
)


class DisclosurePort(Protocol):
    async def search_companies(self, query: str) -> list[DisclosureCompanyHit]: ...
    async def get_company(self, company_id: int) -> DisclosureCompany: ...
    async def list_files(
        self, company_id: int, section: FileSection
    ) -> list[DisclosureFileRow]: ...
    async def download(self, file_id: int) -> DownloadedFile: ...
