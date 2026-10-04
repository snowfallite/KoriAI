"""Pages of e-disclosure.ru as DTOs (tech.md §8.5).

Selectors and edge cases come from the S1-12 discovery: docs/sources/e-disclosure.md.
"""

import contextlib
import re
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any
from urllib.parse import urlsplit

from selectolax.lexbor import LexborHTMLParser, LexborNode

from app.contracts.common import FileSection
from app.contracts.disclosure import DisclosureCompany, DisclosureCompanyHit, DisclosureFileRow
from app.core.time import MSK

# FileSection -> the type parameter of files.aspx.
SECTIONS: dict[FileSection, int] = {
    "charter": 1,
    "annual": 2,
    "ras": 3,
    "ifrs": 4,
    "issuer_reports": 5,
    "affiliates": 6,
    "emission": 7,
    "investors": 8,
    "other": 10,
    "meetings": 16,
}
# The site writes visitor data into the DOM (userIp of Metrika, ad sessions, form tokens):
# what we store keeps only markup.
NOT_MARKUP = ["script", "style", "iframe", "noscript", "link"]
# The 403 page of the site: "If you are not a bot, please copy the report...".
BLOCK_PAGE = "#REQUEST-ID"
# A page of the site has one of these; the ServicePipe check and the 403 page have none.
REAL_PAGE = '#loginForm, #textfield, table.files-table, a[href*="FileLoad"], a[href*="files.aspx"]'
# The captcha of the site lives here: /xpvnsulc/?back_location=...
CAPTCHA_PATH = "/xpvnsulc/"

type RobotsRules = list[tuple[int, bool, re.Pattern[str]]]


def _text(node: LexborNode) -> str:
    # Soft hyphens break header words; non-breaking spaces sit in sizes ("zip, 2.09 МБ").
    return " ".join(node.text(separator=" ").replace("\xad", "").split())


def _day(text: str) -> date | None:
    try:
        return datetime.strptime(text, "%d.%m.%Y").date()  # noqa: DTZ007 - a calendar date
    except ValueError:
        return None


def parse_company(html: str, company_id: int, page_url: str) -> DisclosureCompany | None:
    """The «Общие сведения» block of a card; None when the page has no card."""
    tree = LexborHTMLParser(html)
    fields = {}
    for label in tree.css("table.company-table td.field-name"):
        value = label.next
        while value is not None and value.tag != "td":
            value = value.next
        if value is not None:
            fields[_text(label)] = _text(value)
    full_name = fields.get("Полное наименование компании")
    if not full_name:
        return None
    heading = tree.css_first(".infoblock h2")
    return DisclosureCompany(
        company_id=company_id,
        full_name=full_name,
        short_name=fields.get("Сокращенное наименование компании")
        or (_text(heading) if heading else full_name),
        # A foreign issuer has neither (En+ Group plc).
        inn=fields.get("ИНН") or None,
        ogrn=fields.get("Номер Государственной регистрации (ОГРН)") or None,
        # Some cards give only the place of the company.
        address=fields.get("Адрес Субъекта раскрытия, указанный в ЕГРЮЛ")
        or fields.get("Место нахождения")
        or None,
        page_url=page_url,
    )


def _description(row: LexborNode) -> str | None:
    after = row.next
    while after is not None and after.tag != "tr":
        after = after.next
    if after is None or "description-row" not in (after.attributes.get("class") or ""):
        return None
    return _text(after) or None


def parse_files(html: str, section: FileSection, page_url: str) -> list[DisclosureFileRow]:
    """The rows of table.files-table; a section without files has no table."""
    table = LexborHTMLParser(html).css_first("table.files-table")
    if table is None:
        return []
    header = [_text(th) for th in table.css("th")]
    # The column set differs by section: only the labels tell the columns apart.
    period = next((h for h in header if h.startswith("Отчетн")), None)
    basis = next((h for h in header if h.startswith("Дата наступления основания")), None)
    rows = []
    for row in table.css("tr"):
        link = row.css_first("a.file-link")
        if link is None:
            continue
        cells = dict(zip(header, (_text(td) for td in row.css("td")), strict=False))
        published = _day(cells.get("Дата размещения", ""))
        file_id = link.attributes.get("data-fileid") or ""
        if published is None or not file_id.isdigit():
            continue
        ext, _, size = _text(link).partition(",")
        type_cell = row.css_first("td.type-cell")
        rows.append(
            DisclosureFileRow(
                file_id=int(file_id),
                section=section,
                doc_type_raw=_text(type_cell) if type_cell else "",
                period_raw=cells.get(period, "") if period else "",
                description=_description(row),
                basis_date=_day(cells.get(basis, "")) if basis else None,
                published_date=published,
                file_ext=ext.strip().lower(),
                size_raw=size.strip(),
                page_url=page_url,
                download_url=link.attributes.get("href") or "",
            )
        )
    return rows


def parse_hits(payload: Mapping[str, Any]) -> list[DisclosureCompanyHit]:
    """foundCompaniesList of POST /api/search/companies; its times are Moscow time."""
    hits = []
    for item in payload.get("foundCompaniesList") or []:
        activity = None
        with contextlib.suppress(TypeError, ValueError):
            activity = datetime.fromisoformat(item.get("lastActivity")).replace(tzinfo=MSK)
        hits.append(
            DisclosureCompanyHit(
                company_id=item["id"],
                name=item["name"],
                region=item.get("region") or None,
                branch=item.get("branch") or None,
                last_activity=activity,
                doc_count=item.get("docCount"),
            )
        )
    return hits


def sanitize(html: str, own_host: str) -> str:
    """Markup only: no scripts, styles, frames, form tokens or third-party images."""
    tree = LexborHTMLParser(html)
    tree.strip_tags(NOT_MARKUP)
    for node in tree.css('input[name="__RequestVerificationToken"]'):
        node.attrs["value"] = ""
    for node in tree.css("img[src]"):
        if urlsplit(node.attributes.get("src") or "").netloc not in {"", own_host}:
            node.decompose()
    return tree.html or ""


def parse_robots(text: str) -> tuple[RobotsRules, float]:
    """Allow and Disallow of the `*` group with RFC 9309 wildcards, and Crawl-delay.

    urllib.robotparser compares plain prefixes and would let `/api/*` through.
    """
    rules: RobotsRules = []
    delay = 0.0
    applies = after_agent = False
    for line in text.splitlines():
        key, _, value = line.split("#", 1)[0].partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            # Consecutive User-agent lines open one group.
            applies = (applies and after_agent) or value == "*"
            after_agent = True
            continue
        after_agent = False
        if not applies:
            continue
        if key in {"allow", "disallow"} and value:
            pattern = re.escape(value).replace(r"\*", ".*")
            if pattern.endswith(r"\$"):
                pattern = pattern[:-2] + "$"
            rules.append((len(value), key == "allow", re.compile(pattern)))
        elif key == "crawl-delay":
            with contextlib.suppress(ValueError):
                delay = float(value)
    return rules, delay


def robots_allow(rules: RobotsRules, url: str) -> bool:
    """The longest matching rule wins, Allow wins a tie (RFC 9309 §2.2.2)."""
    parts = urlsplit(url)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    hits = [(length, allow) for length, allow, pattern in rules if pattern.match(path)]
    return max(hits, default=(0, True))[1]
