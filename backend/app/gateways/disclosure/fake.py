"""Disclosure fake (tech.md §8.1, §8.5): answers from backend/fixtures/seed/edisclosure.

companies.yaml holds the cards, files/<company_id>.yaml the rows of their sections,
archives/<file_id>/<name> the files a download gets.
"""

import asyncio
import functools
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from app.contracts.common import FileSection
from app.contracts.disclosure import (
    DisclosureCompany,
    DisclosureCompanyHit,
    DisclosureFileRow,
    DownloadedFile,
)
from app.core.errors import PermanentGatewayError
from app.gateways.disclosure.edisclosure import download_key
from app.gateways.fakes import Fake, port_method
from app.gateways.files.port import FilesPort
from app.gateways.fixtures import SEED, load

ROOT = SEED / "edisclosure"


@dataclass(frozen=True)
class Seed:
    companies: dict[int, DisclosureCompany]
    files: dict[int, list[DisclosureFileRow]]
    archives: dict[int, Path]


@functools.cache
def seed() -> Seed:
    rows = TypeAdapter(list[DisclosureFileRow])
    return Seed(
        companies={
            c.company_id: c
            for c in load(ROOT / "companies.yaml", TypeAdapter(list[DisclosureCompany]))
        },
        files={int(p.stem): load(p, rows) for p in sorted((ROOT / "files").glob("*.yaml"))},
        archives={
            int(folder.name): next(folder.iterdir())
            for folder in sorted((ROOT / "archives").iterdir())
        },
    )


def _nothing(arguments: dict[str, Any]) -> list[Any]:
    return []


class FakeDisclosure(Fake):
    port = "disclosure"
    unavailable = "disclosure_unavailable"
    rate_limited = "disclosure_unavailable"  # a captcha or a 403 of the site (§8.5)

    def __init__(self, files: FilesPort, **options: Any) -> None:
        super().__init__(**options)
        self.seed = seed()
        self._files = files

    @port_method(empty=_nothing)
    async def search_companies(self, query: str) -> list[DisclosureCompanyHit]:
        # The site finds a company by a part of its name, its INN or OGRN.
        needle = query.strip().casefold()
        return [
            DisclosureCompanyHit(
                company_id=c.company_id,
                name=c.short_name,
                region=None,
                branch=None,
                last_activity=None,
                doc_count=len(self.seed.files.get(c.company_id, [])),
            )
            for c in self.seed.companies.values()
            if needle
            and (
                needle in c.full_name.casefold()
                or needle in c.short_name.casefold()
                or needle in {c.inn, c.ogrn}
            )
        ]

    @port_method()
    async def get_company(self, company_id: int) -> DisclosureCompany:
        if company_id not in self.seed.companies:
            raise PermanentGatewayError("not_found")
        return self.seed.companies[company_id]

    @port_method(empty=_nothing)
    async def list_files(self, company_id: int, section: FileSection) -> list[DisclosureFileRow]:
        # A section without files redirects to the card: no rows, no error.
        return [row for row in self.seed.files.get(company_id, []) if row.section == section]

    @port_method()
    async def download(self, file_id: int) -> DownloadedFile:
        source = self.seed.archives.get(file_id)
        if source is None:
            self.no_fixture(f"download of file {file_id}")
            raise PermanentGatewayError("not_found")
        data = await asyncio.to_thread(source.read_bytes)
        stored = await self._files.put(download_key(file_id, source.name), data)
        return DownloadedFile(
            file_id=file_id,
            filename=source.name,
            content_type=mimetypes.guess_type(source.name)[0] or "application/octet-stream",
            size=stored.size,
            sha256=stored.sha256,
            storage_key=stored.key,
        )
