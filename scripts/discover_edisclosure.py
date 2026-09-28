"""e-disclosure discovery for S1-12 (tech.md §8.5, §22.1).

The site answers plain HTTP clients with 403 and puts the ServicePipe JavaScript check in front
of its pages, so the crawl drives a visible Chromium through Playwright with the browser's own
User-Agent. A captcha, if one shows up, is passed by hand in that window.

robots.txt disallows /api/*, and the company search of the site runs through it, so the crawl
never searches: company ids come from ISSUERS and the INN on each card confirms them.

Polite: robots.txt first (RFC 9309 wildcards), one request at a time, 1 / EDISCLOSURE_RPS
seconds between requests, pages and archives cached across runs. Output: snapshots and JSON
summaries in backend/tests/fixtures/edisclosure/ (golden fixtures for F-10), archives in
.discovery/edisclosure/ (gitignored). Hits the real site: run by hand with
`just discover-edisclosure [--headless]`.
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
from urllib.parse import urljoin, urlsplit

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

# key, company id (from memory and web search), INN the card must show, why it is in the sample
ISSUERS = (
    ("sber", 3043, "7707083893", "bank: RAS on bank forms"),
    ("gazp", 934, "7736050003", "gas"),
    ("lkoh", 17, "7708004767", "oil"),
    ("rosn", 6505, "7706107510", "oil"),
    ("mgnt", 7671, "2309085638", "retail"),
    ("rzd", 4543, "7708503727", "bonds only"),
    ("gmkn", 564, "8401005730", "metals and mining"),
    ("mtss", 236, "7740000076", "telecom"),
    ("rual", 38288, "3906394938", "МКПАО: IFRS without RAS candidate"),
    ("ydex", 37211, None, "МКПАО, IT: check the name on the card"),
)
# Pages for the discovery notes: the search form, its script, the terms of use, the paid API.
PAGES = {
    "search/page.html": "/poisk-po-kompaniyam",
    "terms.html": "/usloviya-ispol'zovaniya-informacii",
    "api-gateway.html": "/poluchenie-informacii/shlyuz-api",
}
ASSETS = {"search/ed.search.companies-page.js": "/src/js/ed.search.companies-page.js"}

# The real page has one of these; the ServicePipe check and the 403 page have none.
REAL_PAGE = '#loginForm, #textfield, table.files-table, a[href*="FileLoad"], a[href*="files.aspx"]'
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

Rules = list[tuple[int, bool, re.Pattern[str]]]


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


def parse_robots(text: str) -> tuple[Rules, float]:
    """Allow and Disallow rules and Crawl-delay of the `*` group, with RFC 9309 wildcards.

    urllib.robotparser matches paths as plain prefixes, so it would let `/api/*` through.
    """
    rules: Rules = []
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


def allowed(rules: Rules, url: str) -> bool:
    """The longest matching rule wins, Allow wins a tie (RFC 9309 §2.2.2)."""
    parts = urlsplit(url)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    hits = [(length, allow) for length, allow, pattern in rules if pattern.match(path)]
    return max(hits, default=(0, True))[1]


class Disallowed(Exception):
    pass


class Crawler:
    def __init__(self, page: Page, base: str, delay: float) -> None:
        self.page = page
        self.base = base
        self.delay = delay
        self.next_at = 0.0
        self.tag = "setup"
        self.robots: Rules | None = None
        self.requests: list[dict[str, str]] = []
        index = OUT / "pages.json"
        self.pages: dict[str, dict[str, Any]] = (
            json.loads(index.read_text(encoding="utf-8")) if index.exists() else {}
        )

    def pace(self, url: str, kind: str) -> None:
        """Enforce robots.txt and the pause before every request to the site."""
        if self.robots is not None and not allowed(self.robots, url):
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
                self.page.wait_for_selector(FILE_TABLE, state="attached", timeout=3_000)
        html = self.page.content()
        # A section without files redirects to the card: keep only the redirect.
        file = None if "files.aspx" in url and "files.aspx" not in final_url else name
        if file:
            (OUT / file).parent.mkdir(parents=True, exist_ok=True)
            (OUT / file).write_text(html, encoding="utf-8")
        self.pages[url] = {"final_url": final_url, "file": file}
        dump(OUT / "pages.json", self.pages)
        return final_url, html

    def save(self, url: str, name: str) -> None:
        """Save a static file of the site as is."""
        if (OUT / name).exists():
            return
        self.pace(url, "asset")
        response = self.page.context.request.get(url)
        (OUT / name).parent.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_text(response.text(), encoding="utf-8")


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
    if response.status == 200 and "user-agent" in text.lower():
        rules, delay = parse_robots(text)
    elif 400 <= response.status < 500:
        rules, delay = [], 0.0  # RFC 9309 §2.3.1.3: an unavailable robots.txt has no rules.
    else:
        raise SystemExit(f"robots.txt did not load ({response.status}): stop per RFC 9309")
    crawler.robots = rules
    crawler.delay = max(crawler.delay, delay)
    return f"{response.status}, {len(rules)} rules, crawl-delay {delay or 'none'}"


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


def discover(crawler: Crawler, company_id: int) -> dict[str, Any]:
    result: dict[str, Any] = {"company_id": company_id, "card": card(crawler, company_id)}
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
        header, found = rows(html, crawler.base)
        by_type[file_type] = found
        files[str(file_type)] = {"status": "ok", "header": header, "rows": len(found)}
        dump(OUT / "rows" / f"{company_id}_{file_type}.json", found)
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
            for name, path in PAGES.items():
                summary.setdefault("pages", {})[name] = crawler.open(base + path, name) is not None
            for name, path in ASSETS.items():
                crawler.save(base + path, name)
            for key, company_id, inn, note in ISSUERS:
                crawler.tag = key
                try:
                    result = discover(crawler, company_id)
                except (Disallowed, PlaywrightError) as error:
                    result = {"company_id": company_id, "error": str(error)}
                result |= {"key": key, "inn_expected": inn, "note": note}
                summary["issuers"].append(result)
                files = result.get("files", {})
                inn_on_card = result.get("card", {}).get("inn")
                say(
                    f"{key:<5} id={company_id} inn={inn_on_card}"
                    f"{'' if inn in {None, inn_on_card} else ' MISMATCH'}"
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
