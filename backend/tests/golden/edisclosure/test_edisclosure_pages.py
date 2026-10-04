"""Pages of e-disclosure.ru as DTOs (S1-09; tech.md §8.5) on the S1-12 snapshots.

Expectations are copied from the snapshot markup by hand (§14.1), not from parser output.
"""

# ruff: noqa: RUF001  (the expectations are Russian text of the site)

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from selectolax.lexbor import LexborHTMLParser

from app.contracts.disclosure import DisclosureCompanyHit, DisclosureFileRow
from app.gateways.disclosure.edisclosure.adapter import attachment_name
from app.gateways.disclosure.edisclosure.parse import (
    BLOCK_PAGE,
    REAL_PAGE,
    parse_company,
    parse_files,
    parse_hits,
    parse_robots,
    robots_allow,
    sanitize,
)

SNAPSHOTS = Path(__file__).parents[2] / "fixtures" / "edisclosure"
SITE = "https://www.e-disclosure.ru"


def page(name: str) -> str:
    return (SNAPSHOTS / name).read_text(encoding="utf-8")


def row(file_id: int, section: str, url: str, **fields: object) -> DisclosureFileRow:
    return DisclosureFileRow.model_validate(
        {
            "file_id": file_id,
            "section": section,
            "page_url": url,
            "download_url": f"{SITE}/portal/FileLoad.ashx?Fileid={file_id}",
            "file_ext": "zip",
            "description": None,
            **fields,
        }
    )


def test_a_card_gives_the_general_block() -> None:
    url = f"{SITE}/portal/company.aspx?id=3043"

    card = parse_company(page("company/3043.html"), 3043, url)

    assert card is not None
    assert card.model_dump() == {
        "company_id": 3043,
        "full_name": "Публичное акционерное общество «Сбербанк России»",
        "short_name": "ПАО Сбербанк",
        "inn": "7707083893",
        "ogrn": "1027700132195",
        "address": "117312, г. Москва, ул. Вавилова, д. 19",
        "page_url": url,
    }


def test_a_foreign_issuer_has_no_inn_and_gives_its_place() -> None:
    card = parse_company(page("company/37211.html"), 37211, "u")

    assert card is not None
    assert (card.full_name, card.inn, card.ogrn) == ("En+ Group plc", None, None)
    assert card.address == "44 Esplanade, St Helier, Jersey, JE4 9WG"


def test_a_page_without_a_card_gives_nothing() -> None:
    assert parse_company(page("files/3043_3.html"), 3043, "u") is None


def test_a_reports_section_with_a_period_column() -> None:
    url = f"{SITE}/portal/files.aspx?id=17&type=3"

    rows = parse_files(page("files/17_3.html"), "ras", url)

    assert len(rows) == 61
    assert rows[0] == row(
        1940241,
        "ras",
        url,
        doc_type_raw="Промежуточная бухгалтерская отчетность (все формы)",
        period_raw="2026, 6 месяцев",
        basis_date=date(2026, 7, 29),
        published_date=date(2026, 7, 29),
        size_raw="1.9 МБ",
    )
    assert (rows[2].file_id, rows[2].doc_type_raw, rows[2].period_raw) == (
        1915678,
        "Годовая бухгалтерская отчетность (все формы)",
        "2025",
    )
    assert (rows[2].basis_date, rows[2].published_date) == (date(2026, 3, 19), date(2026, 3, 20))


def test_a_section_without_a_period_column_and_with_descriptions() -> None:
    rows = parse_files(page("files/3043_10.html"), "other", "u")

    assert len(rows) == 78
    first = rows[0]
    assert (first.file_id, first.doc_type_raw, first.period_raw) == (
        1922611,
        "Прочие документы",
        "",
    )
    assert first.description == (
        "Порядок доступа к дистанционному участию в годовом заседании ОСА в 2026 году "
        "и технические требования для участия в заседании"
    )
    assert (first.basis_date, first.published_date, first.size_raw) == (
        date(2026, 4, 21),
        date(2026, 4, 21),
        "87.31 КБ",
    )


def test_a_meetings_section_has_no_basis_date() -> None:
    rows = parse_files(page("files/6505_16.html"), "meetings", "u")

    assert len(rows) == 37
    assert [(r.file_id, r.doc_type_raw, r.period_raw, r.basis_date) for r in rows[:2]] == [
        (1938190, "Годовой отчет", "2025", None),
        (1920924, "Годовая бухгалтерская отчетность (все формы)", "2025", None),
    ]
    assert [r.published_date for r in rows[:2]] == [date(2026, 7, 7), date(2026, 4, 13)]
    assert rows[1].size_raw == "964.23 КБ"


def test_only_the_described_row_gets_the_description() -> None:
    rows = parse_files(page("files/17_8.html"), "investors", "u")

    assert len(rows) == 4
    assert [(r.file_id, r.period_raw, r.description) for r in rows[:2]] == [
        (1938285, "2025", "Отчет об устойчивом развитии Группы «ЛУКОЙЛ» 2025"),
        (1891569, "2024", None),
    ]


def test_ifrs_of_a_foreign_issuer() -> None:
    rows = parse_files(page("files/37211_4.html"), "ifrs", "u")

    assert [
        (r.file_id, r.period_raw, r.basis_date, r.published_date, r.size_raw) for r in rows
    ] == [
        (1503935, "2018", date(2019, 3, 28), date(2019, 4, 1), "5.05 МБ"),
        (1411015, "2017", date(2018, 3, 30), date(2018, 3, 30), "3.93 МБ"),
    ]


def test_a_section_redirected_to_the_card_has_no_rows() -> None:
    assert parse_files(page("company/3043.html"), "charter", "u") == []


def test_a_search_answer_gives_hits_in_utc() -> None:
    answer = json.loads(page("search/companies_7702077840.json"))["response"]

    assert parse_hits(answer) == [
        DisclosureCompanyHit(
            company_id=43,
            name="ПАО Московская Биржа",
            region="Москва",
            branch="Иное",
            # 2026-09-22T14:00:00.02 of the site is Moscow time
            last_activity=datetime(2026, 9, 22, 11, 0, 0, 20000, tzinfo=UTC),
            doc_count=56,
        )
    ]


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("/api/search/companies", False),
        ("/portal/company.aspx?id=3043", True),
        ("/portal/files.aspx?id=3043&type=4", True),
        ("/portal/FileLoad.ashx?Fileid=1940241", True),
        ("/Company/Search?query=x", False),
        ("/PortalImageHandler.ashx?id=1", False),
        ("/Event/Certificate?id=1", False),
        ("/Event/Certificate", True),  # the rule needs the query string
    ],
)
def test_robots_txt_of_the_site(path: str, allowed: bool) -> None:
    rules, delay = parse_robots(page("robots.txt"))

    assert robots_allow(rules, SITE + path) is allowed
    assert delay == 0.0


def test_the_403_page_is_told_apart_from_a_real_page() -> None:
    blocked, real = (
        LexborHTMLParser(page("blocked_403.html")),
        LexborHTMLParser(page("files/17_3.html")),
    )

    assert blocked.css_first(BLOCK_PAGE) is not None
    assert blocked.css_first(REAL_PAGE) is None
    assert real.css_first(REAL_PAGE) is not None
    assert real.css_first(BLOCK_PAGE) is None


def test_stored_html_keeps_only_markup() -> None:
    raw = (
        "<html><head><script>var userIp='1.2.3.4'</script><style>p{}</style></head><body>"
        "<form><input name='__RequestVerificationToken' value='secret'></form>"
        "<img src='https://ads.example/x.png'><img src='/images/logo.png'>"
        "<iframe src='https://ads.example'></iframe><table class='files-table'></table>"
        "</body></html>"
    )

    clean = sanitize(raw, "www.e-disclosure.ru")

    for gone in ("userIp", "<style", "secret", "ads.example", "<iframe"):
        assert gone not in clean
    assert "/images/logo.png" in clean
    assert "files-table" in clean


@pytest.mark.parametrize(
    ("header", "name"),
    [
        # what the portal sends (docs/sources/e-disclosure.md, section 3)
        (
            "attachment; filename=MSFO_6m2026.pdf.zip; filename*=UTF-8''MSFO_6m2026.pdf.zip",
            "MSFO_6m2026.pdf.zip",
        ),
        ("attachment; filename*=UTF-8''%D0%9E%D1%82%D1%87%D0%B5%D1%82.rar", "Отчет.rar"),
        ("attachment; filename=report.7z", "report.7z"),
        (None, "1940241.bin"),
    ],
)
def test_the_name_of_a_downloaded_file(header: str | None, name: str) -> None:
    assert attachment_name(header, "1940241.bin") == name
