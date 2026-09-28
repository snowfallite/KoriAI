"""e-disclosure discovery for S1-12 (tech.md §8.5, §22.1).

The site answers plain HTTP clients with 403 and puts the ServicePipe JavaScript check in front
of its pages, so the crawl drives a visible Chromium through Playwright with the browser's own
User-Agent. A captcha, if one shows up, is passed by hand in that window.

Polite: robots.txt first, one request at a time, 1 / EDISCLOSURE_RPS seconds between requests,
pages, searches and archives cached across runs. Output: snapshots and JSON summaries in
backend/tests/fixtures/edisclosure/ (golden fixtures for F-10), archives in .discovery/edisclosure/
(gitignored). Hits the real site: run by hand with `just discover-edisclosure [--headless]`.
"""

# ruff: noqa: RUF001  (Russian names and units are data here)

import contextlib
import io
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright
from selectolax.parser import HTMLParser, Node

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend/tests/fixtures/edisclosure"
ARCHIVES = ROOT / ".discovery/edisclosure"

# FileSection -> the files.aspx type parameter (§8.5).
SECTIONS = {
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
# Archives to sample per issuer: the first row of each section in this order, then the second.
SAMPLE_ORDER = (4, 3, 2, 8, 10)
SAMPLES = 5
MAX_ARCHIVE_BYTES = 50 * 2**20

# key, INN (None: the name search only), name for the name search, why it is in the sample
ISSUERS = (
    ("sber", "7707083893", "Сбербанк", "bank: RAS on bank forms"),
    ("lkoh", "7708004767", "ЛУКОЙЛ", "oil and gas"),
    ("mgnt", "2309085638", "Магнит", "retail"),
    ("rzd", "7708503727", "Российские железные дороги", "bonds only"),
    ("rual", "3906394938", "РУСАЛ", "МКПАО: IFRS without RAS candidate"),
    ("ydex", None, "Яндекс", "МКПАО, IT"),
    ("gmkn", "8401005730", "Норильский никель", "metals and mining"),
    ("mtss", "7740000076", "МТС", "telecom"),
    ("irao", "2320109650", "Интер РАО", "power"),
    ("moex", "7702077840", "Московская Биржа", "exchange"),
)

# The real page has one of these; the ServicePipe check and the 403 page have none.
REAL_PAGE = '#textfield, table.files-table, a[href*="FileLoad"], a[href*="files.aspx"]'
FILE_TABLE = 'table.files-table, a[href*="FileLoad"]'
# 403 page of the site: "If you are not a bot, please copy the report..."
BLOCK_PAGE = "#REQUEST-ID"
FIRST_PAGE_WAIT_MS = 300_000  # time to pass a captcha by hand
PAGE_WAIT_MS = 60_000

MAGIC = {
    b"PK\x03\x04": "zip",
    b"%PDF": "pdf",
    b"Rar!": "rar",
    b"7z\xbc\xaf": "7z",
    b"\xd0\xcf\x11\xe0": "ole",
}
OOXML = (".xlsx", ".xlsm", ".docx", ".pptx")
CYRILLIC = re.compile("[А-Яа-яЁё]")
SIZE = re.compile(r"(\d+(?:[.,]\d+)?)\s*([КМГKMG])[БB]", re.IGNORECASE)
UNITS = {"к": 2**10, "k": 2**10, "м": 2**20, "m": 2**20, "г": 2**30, "g": 2**30}


def setting(key: str, default: str) -> str:
    """Read a key the way app/config.py does: the environment first, then the repo .env."""
    if key in os.environ:
        return os.environ[key]
    env = ROOT / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    pairs = (line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))
    return {k.strip(): v.strip() for k, v in pairs}.get(key, default)


def say(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def dump(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class Disallowed(Exception):
    pass


class Crawler:
    def __init__(self, page: Page, base: str, delay: float) -> None:
        self.page = page
        self.base = base
        self.delay = delay
        self.next_at = 0.0
        self.tag = "setup"
        self.robots: RobotFileParser | None = None
        self.requests: list[dict[str, str]] = []
        index = OUT / "pages.json"
        self.pages: dict[str, dict[str, Any]] = (
            json.loads(index.read_text(encoding="utf-8")) if index.exists() else {}
        )

    def pace(self, url: str, kind: str) -> None:
        """Enforce robots.txt and the pause before every request to the site."""
        if self.robots is not None and not self.robots.can_fetch("*", url):
            raise Disallowed(url)
        time.sleep(max(0.0, self.next_at - time.monotonic()))
        self.next_at = time.monotonic() + self.delay
        self.requests.append({"issuer": self.tag, "kind": kind, "url": url})

    def goto(self, url: str) -> None:
        try:
            self.page.goto(url, wait_until="domcontentloaded")
        except PlaywrightError as error:
            # The browser check reloads the page while goto still waits for the first load.
            if "interrupted by another navigation" not in str(error):
                raise

    def open(self, url: str, name: str) -> tuple[str, str] | None:
        """Show a page in the browser and save its DOM; None when only a stub shows up."""
        cached = self.pages.get(url)
        if cached and (cached["file"] is None or (OUT / cached["file"]).exists()):
            html = (OUT / cached["file"]).read_text(encoding="utf-8") if cached["file"] else ""
            return cached["final_url"], html
        self.pace(url, "page")
        self.goto(url)
        try:
            self.page.wait_for_selector(
                f"{REAL_PAGE}, {BLOCK_PAGE}", state="attached", timeout=PAGE_WAIT_MS
            )
        except PlaywrightError:
            return None
        if self.page.query_selector(BLOCK_PAGE):
            return None
        final_url = self.page.url
        if "files.aspx" in final_url:
            # A section page may have no rows at all.
            with contextlib.suppress(PlaywrightError):
                self.page.wait_for_selector(FILE_TABLE, state="attached", timeout=10_000)
        html = self.page.content()
        # A section without files redirects to the card: keep only the redirect.
        file = None if "files.aspx" in url and "files.aspx" not in final_url else name
        if file:
            (OUT / file).parent.mkdir(parents=True, exist_ok=True)
            (OUT / file).write_text(html, encoding="utf-8")
        self.pages[url] = {"final_url": final_url, "file": file}
        dump(OUT / "pages.json", self.pages)
        return final_url, html


def load_robots(crawler: Crawler) -> str:
    url = f"{crawler.base}/robots.txt"
    say("A Chromium window opens. If it shows a captcha, pass it there.")
    crawler.pace(url, "robots")
    crawler.goto(url)
    # robots.txt comes as text/plain once the browser check is passed; without the file
    # the wait times out and the status below decides.
    with contextlib.suppress(PlaywrightError):
        crawler.page.wait_for_function(
            "() => document.contentType === 'text/plain'"
            f" || !!document.querySelector('{BLOCK_PAGE}, {REAL_PAGE}')",
            timeout=FIRST_PAGE_WAIT_MS,
        )
    if crawler.page.query_selector(BLOCK_PAGE):
        raise SystemExit("403 from the site: this IP is blocked, try without a VPN")
    crawler.pace(url, "robots")
    response = crawler.page.context.request.get(url)
    text = response.text()
    (OUT / "robots.txt").write_text(text, encoding="utf-8")
    robots = RobotFileParser()
    if response.status == 200 and "user-agent" in text.lower():
        robots.parse(text.splitlines())
    elif 400 <= response.status < 500:
        robots.allow_all = True  # RFC 9309 §2.3.1.3: an unavailable robots.txt has no rules.
    else:
        raise SystemExit(f"robots.txt did not load ({response.status}): stop per RFC 9309")
    crawler.robots = robots
    crawler.delay = max(crawler.delay, float(robots.crawl_delay("*") or 0))
    return f"{response.status}, crawl-delay {robots.crawl_delay('*')}"


def to_search_form(crawler: Crawler) -> None:
    if "poisk-po-kompaniyam" in crawler.page.url:
        return
    url = f"{crawler.base}/poisk-po-kompaniyam"
    crawler.pace(url, "page")
    crawler.goto(url)
    crawler.page.wait_for_selector("#textfield", state="attached", timeout=PAGE_WAIT_MS)


def search(crawler: Crawler, query: str, name: str) -> dict[str, Any]:
    """Run the company search form and keep what the page asked the server for."""
    path = OUT / "search" / f"{name}.json"
    if path.exists():
        cached: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return cached
    to_search_form(crawler)
    page = crawler.page
    page.fill("#textfield", query)
    crawler.pace(page.url, "search")
    api: dict[str, Any]
    try:
        with page.expect_response(
            lambda r: (
                r.request.resource_type in {"xhr", "fetch"} and r.url.startswith(crawler.base)
            ),
            timeout=30_000,
        ) as info:
            page.press("#textfield", "Enter")
        response = info.value
        api = {
            "method": response.request.method,
            "url": response.url,
            "status": response.status,
            "request_headers": {
                k: v for k, v in response.request.headers.items() if k.lower() != "cookie"
            },
            "post_data": response.request.post_data,
            "body": response.text(),
        }
        if crawler.robots is not None and not crawler.robots.can_fetch("*", response.url):
            raise Disallowed(response.url)
    except PlaywrightError as error:
        api = {"error": str(error)}
    page.wait_for_timeout(1500)  # let the page render the answer
    scope = "#searchResults " if page.query_selector("#searchResults") else ""
    links = page.eval_on_selector_all(
        f'{scope}a[href*="company.aspx?id="]',
        "els => els.map(e => ({href: e.href, text: e.innerText.trim(),"
        " row: (e.closest('tr') || e.parentElement).innerText.trim().slice(0, 300)}))",
    )
    result = {"query": query, "api": api, "links": links, "candidates": candidates(api, links)}
    dump(path, result)
    return result


def candidates(api: dict[str, Any], links: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Company ids from the result links, else from the JSON answer of the search request."""
    found: list[dict[str, Any]] = []
    for link in links:
        match = re.search(r"company\.aspx\?id=(\d+)", link["href"])
        if match and all(hit["company_id"] != int(match.group(1)) for hit in found):
            found.append({"company_id": int(match.group(1)), "name": link["text"]})
    if found:
        return found

    def walk(node: object) -> None:
        if isinstance(node, dict):
            ids = [k for k in node if k.lower() in {"id", "companyid"}]
            names = [k for k in node if "name" in k.lower()]
            if ids and names:
                found.append({"company_id": node[ids[0]], "name": node[names[0]]})
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    with contextlib.suppress(ValueError):
        walk(json.loads(api.get("body") or "null"))
    return found


def card(crawler: Crawler, company_id: int) -> dict[str, Any]:
    url = f"{crawler.base}/portal/company.aspx?id={company_id}"
    opened = crawler.open(url, f"company/{company_id}.html")
    if opened is None:
        return {"status": "stub"}
    tree = HTMLParser(opened[1])
    text = tree.body.text(separator=" ") if tree.body else ""
    inn = re.search(r"ИНН\D{0,20}?(\d{10,12})", text)
    ogrn = re.search(r"ОГРН\D{0,20}?(\d{13,15})", text)
    sections: dict[str, str] = {}
    for link in tree.css('a[href*="files.aspx"]'):
        match = re.search(r"type=(\d+)", link.attributes.get("href") or "")
        if match:
            sections.setdefault(match.group(1), link.text(strip=True))
    title = tree.css_first("title")
    return {
        "status": "ok",
        "title": title.text(strip=True) if title else None,
        "inn": inn.group(1) if inn else None,
        "ogrn": ogrn.group(1) if ogrn else None,
        "sections": sections,
    }


def ancestor(node: Node | None, tag: str) -> Node | None:
    while node is not None and node.tag != tag:
        node = node.parent
    return node


def rows(html: str, base: str) -> tuple[list[str], list[dict[str, Any]]]:
    """Header cells and file rows of a files.aspx page."""
    tree = HTMLParser(html)
    links = [a for a in tree.css("a[href]") if "fileload" in (a.attributes["href"] or "").lower()]
    table = ancestor(links[0], "table") if links else None
    header = [th.text(strip=True) for th in table.css("th")] if table else []
    found = []
    for link in links:
        href = urljoin(base + "/portal/", link.attributes.get("href") or "")
        row = ancestor(link, "tr")
        cells = [c.text(separator=" ", strip=True) for c in row.iter()] if row else []
        file_id = re.search(r"Fileid=(\d+)", href, re.IGNORECASE)
        found.append(
            {
                "file_id": int(file_id.group(1)) if file_id else None,
                "href": href,
                "link_text": link.text(separator=" ", strip=True),
                "cells": cells,
            }
        )
    return header, found


def size_bytes(text: str) -> int | None:
    match = SIZE.search(text)
    if not match:
        return None
    return int(float(match.group(1).replace(",", ".")) * UNITS[match.group(2).lower()])


def decode_name(raw: bytes, utf8_flag: bool) -> tuple[str, str]:
    if utf8_flag:
        return raw.decode("utf-8", "replace"), "utf-8 flag"
    if raw.isascii():
        return raw.decode("ascii"), "ascii"
    try:
        return raw.decode("utf-8"), "utf-8 without flag"
    except UnicodeDecodeError:
        pass
    # Windows zip tools write the DOS code page cp866; cp1251 shows up too.
    decoded = [(raw.decode(encoding), encoding) for encoding in ("cp866", "cp1251")]
    return max(decoded, key=lambda pair: len(CYRILLIC.findall(pair[0])))


def describe(data: bytes, name: str = "", depth: int = 0) -> dict[str, Any]:
    """File kind by magic bytes; zip archives are listed with nested archives inside."""
    kind = next((k for magic, k in MAGIC.items() if data.startswith(magic)), "other")
    if kind == "zip" and name.lower().endswith(OOXML):
        kind = "ooxml"
    elif kind == "other" and data.lstrip()[:1] == b"<":
        kind = "markup"
    info: dict[str, Any] = {"kind": kind, "bytes": len(data)}
    if kind == "zip" and depth < 3:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = []
                for item in archive.infolist():
                    if item.is_dir():
                        continue
                    utf8 = bool(item.flag_bits & 0x800)
                    raw = item.filename.encode("utf-8" if utf8 else "cp437")
                    entry_name, encoding = decode_name(raw, utf8)
                    entry: dict[str, Any] = {"name": entry_name, "name_encoding": encoding}
                    if item.file_size <= MAX_ARCHIVE_BYTES:
                        entry |= describe(archive.read(item), entry_name, depth + 1)
                    else:
                        entry |= {"kind": "skipped", "bytes": item.file_size}
                    entries.append(entry)
                info["entries"] = entries
        except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as error:
            info["error"] = str(error)
    return info


def download(crawler: Crawler, row: dict[str, Any]) -> dict[str, Any]:
    target = ARCHIVES / str(row["file_id"])
    info: dict[str, Any] = {"file_id": row["file_id"], "cells": row["cells"]}
    size = size_bytes(row["link_text"]) or size_bytes(" ".join(row["cells"]))
    if size and size > MAX_ARCHIVE_BYTES:
        return info | {"status": "skipped", "declared_bytes": size}
    meta = target.with_suffix(".json")
    if not (target.exists() and meta.exists()):
        crawler.pace(row["href"], "download")
        response = crawler.page.context.request.get(row["href"], timeout=300_000)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.body())
        headers = response.headers
        dump(
            meta,
            {
                "status": response.status,
                "content_type": headers.get("content-type"),
                "content_disposition": headers.get("content-disposition"),
            },
        )
    return info | json.loads(meta.read_text(encoding="utf-8")) | describe(target.read_bytes())


def discover(crawler: Crawler, key: str, inn: str | None, name: str) -> dict[str, Any]:
    result: dict[str, Any] = {"key": key, "inn_query": inn, "name_query": name}
    found = {"name": search(crawler, name, f"{key}_name")}
    if inn:
        found["inn"] = search(crawler, inn, f"{key}_inn")
    result["search"] = {mode: len(hit["candidates"]) for mode, hit in found.items()}
    hits = found.get("inn", {}).get("candidates") or found["name"]["candidates"]
    if not hits:
        return result | {"error": "not found"}
    company_id = int(hits[0]["company_id"])
    result["company_id"] = company_id
    result["card"] = card(crawler, company_id)

    types = set(SECTIONS.values()) | {int(t) for t in result["card"].get("sections", {})}
    files: dict[str, Any] = {}
    by_type: dict[int, list[dict[str, Any]]] = {}
    for file_type in sorted(types):
        url = f"{crawler.base}/portal/files.aspx?id={company_id}&type={file_type}"
        opened = crawler.open(url, f"files/{company_id}_{file_type}.html")
        if opened is None:
            files[str(file_type)] = {"status": "stub"}
            continue
        final_url, html = opened
        if "files.aspx" not in final_url:
            files[str(file_type)] = {"status": "empty", "redirect": final_url}
            continue
        header, found_rows = rows(html, crawler.base)
        by_type[file_type] = found_rows
        files[str(file_type)] = {"status": "ok", "header": header, "rows": len(found_rows)}
        dump(OUT / "rows" / f"{company_id}_{file_type}.json", found_rows)
    result["files"] = files

    picked: list[dict[str, Any]] = []
    for position in range(SAMPLES):
        for file_type in SAMPLE_ORDER:
            section = [r for r in by_type.get(file_type, []) if r["file_id"]]
            if position < len(section) and len(picked) < SAMPLES:
                picked.append(section[position] | {"type": file_type})
    downloads = []
    for row in picked:
        try:
            downloads.append(download(crawler, row) | {"type": row["type"]})
        except (Disallowed, PlaywrightError) as error:
            downloads.append({"file_id": row["file_id"], "error": str(error)})
    result["downloads"] = downloads
    return result


def main() -> int:
    base = setting("EDISCLOSURE_BASE_URL", "https://www.e-disclosure.ru").rstrip("/")
    delay = 1 / float(setting("EDISCLOSURE_RPS", "0.5"))
    OUT.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"issuers": []}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless="--headless" in sys.argv)
        # Pin the context to the browser's own User-Agent: API requests then match the page.
        probe = browser.new_page()
        agent = probe.evaluate("navigator.userAgent")
        probe.close()
        context = browser.new_context(user_agent=agent, locale="ru-RU")
        crawler = Crawler(context.new_page(), base, delay)
        try:
            summary["user_agent"] = agent
            summary["robots"] = load_robots(crawler)
            say(f"robots.txt: {summary['robots']}")
            if crawler.open(f"{base}/poisk-po-kompaniyam", "search/page.html") is None:
                raise SystemExit("the search page did not load")
            for key, inn, name, note in ISSUERS:
                crawler.tag = key
                try:
                    result = discover(crawler, key, inn, name) | {"note": note}
                except (Disallowed, PlaywrightError) as error:
                    result = {"key": key, "error": str(error)}
                summary["issuers"].append(result)
                files = result.get("files", {})
                inn_on_card = result.get("card", {}).get("inn")
                say(
                    f"{key:<5} id={result.get('company_id')} inn={inn_on_card}"
                    f" sections={sum(f['status'] == 'ok' for f in files.values())}/{len(files)}"
                    f" downloads={len(result.get('downloads', []))} {result.get('error', '')}"
                )
        finally:
            summary["requests"] = crawler.requests
            dump(OUT / "summary.json", summary)
            browser.close()
    say(f"{len(crawler.requests)} requests, summary in {OUT.relative_to(ROOT)}/summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
