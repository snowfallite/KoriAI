"""e-disclosure.ru behind DisclosurePort (tech.md §8.5): a windowed Firefox through Playwright.

Without a browser the site answers 403 or a JavaScript check, a headless one gets a captcha
(S1-12). A persistent profile keeps the cookies of the check (400 days). One page, one request
at a time, at most EDISCLOSURE_RPS; robots.txt rules everything but the company search, which
the owner allowed. A server without a display gets Xvfb started for the browser.
"""

import asyncio
import contextlib
import hashlib
import json
import os
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from email.message import Message
from typing import Any
from urllib.parse import urlencode, urlsplit

import structlog
from playwright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout

from app.config import Settings
from app.contracts.common import FileSection
from app.contracts.disclosure import (
    DisclosureCompany,
    DisclosureCompanyHit,
    DisclosureFileRow,
    DownloadedFile,
)
from app.core.errors import PermanentGatewayError, TransientGatewayError
from app.gateways.disclosure.edisclosure import download_key
from app.gateways.disclosure.edisclosure.parse import (
    BLOCK_PAGE,
    CAPTCHA_PATH,
    REAL_PAGE,
    SECTIONS,
    RobotsRules,
    parse_company,
    parse_files,
    parse_hits,
    parse_robots,
    robots_allow,
    sanitize,
)
from app.gateways.files.port import FilesPort
from app.gateways.retry import backoff

log = structlog.get_logger(__name__)

PAGE_WAIT_MS = 60_000
DOWNLOAD_WAIT_MS = 300_000
HTML_TTL = timedelta(hours=6)
RETRIES = 3  # 5xx and timeouts; a captcha or a 403 goes up at once
SEARCH_PAGE = "/poisk-po-kompaniyam"
SEARCH_API = "/api/search/companies"
# The form of the search page posts the same fields (S1-12).
SEARCH_JS = """async ([url, body]) => {
  const answer = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest",
      "Accept": "application/json",
    },
    body,
  });
  return {status: answer.status, text: await answer.text()};
}"""


class _Flaky(Exception):
    """A 5xx or a timeout of the site: worth another try."""


def attachment_name(header: str | None, fallback: str) -> str:
    """The file name of Content-Disposition; filename* (RFC 6266) wins over filename."""
    message = Message()
    message["content-disposition"] = header or ""
    return message.get_filename() or fallback


class EDisclosure:
    def __init__(self, settings: Settings, files: FilesPort) -> None:
        self._base = settings.EDISCLOSURE_BASE_URL.rstrip("/")
        self._host = urlsplit(self._base).netloc
        self._delay_s = 1 / settings.EDISCLOSURE_RPS
        self._profile = settings.DATA_DIR / "edisclosure" / "profile"
        self._files = files
        self._lock = asyncio.Lock()
        self._next_at = 0.0
        self._robots: RobotsRules | None = None
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._display: asyncio.subprocess.Process | None = None

    async def aclose(self) -> None:
        # No lock: a shutdown does not wait for a download; the step in flight just fails.
        await self._close_browser()
        if self._display is not None and self._display.returncode is None:
            self._display.terminate()
            await self._display.wait()
        self._display = None

    async def search_companies(self, query: str) -> list[DisclosureCompanyHit]:
        body = urlencode(
            {
                "textfield": query,
                "radReg": "FederalDistricts",
                "districtsCheckboxGroup": "-1",
                "regionsCheckboxGroup": "-1",
                "branchesCheckboxGroup": "-1",
                "lastPageSize": "10",
                "lastPageNumber": "1",
                "query": query,
            }
        )

        async def post(page: Page) -> dict[str, Any]:
            if not page.url.startswith(self._base):  # the fetch needs the site's own page
                await self._open(page, self._base + SEARCH_PAGE)
            # robots.txt disallows /api/*: the search goes there by the owner's call (§8.5).
            await self._pace(self._base + SEARCH_API, robots=False)
            answer = await page.evaluate(SEARCH_JS, [self._base + SEARCH_API, body])
            if answer["status"] >= 500:
                raise _Flaky(f"search answered {answer['status']}")
            if answer["status"] != 200:
                raise TransientGatewayError("disclosure_unavailable")
            found: dict[str, Any] = json.loads(answer["text"])
            return found

        return parse_hits(await self._browse(post))

    async def get_company(self, company_id: int) -> DisclosureCompany:
        url = f"{self._base}/portal/company.aspx?id={company_id}"
        card = parse_company(await self._html(url), company_id, url)
        if card is None:
            raise PermanentGatewayError("not_found")
        return card

    async def list_files(self, company_id: int, section: FileSection) -> list[DisclosureFileRow]:
        url = f"{self._base}/portal/files.aspx?id={company_id}&type={SECTIONS[section]}"
        # A section without files redirects to the card, which has no table of files.
        return parse_files(await self._html(url), section, url)

    async def download(self, file_id: int) -> DownloadedFile:
        url = f"{self._base}/portal/FileLoad.ashx?Fileid={file_id}"

        async def get(page: Page) -> tuple[bytes, str, str]:
            await self._pace(url)
            # From the browser context: the cookies and the fingerprint of the check go along.
            answer = await page.context.request.get(url, timeout=DOWNLOAD_WAIT_MS)
            content_type = answer.headers.get("content-type", "application/octet-stream")
            if answer.status >= 500:
                raise _Flaky(f"download answered {answer.status}")
            if answer.status == 404:
                raise PermanentGatewayError("not_found")
            if not answer.ok or content_type.startswith("text/html"):  # a check, not a file
                raise TransientGatewayError("disclosure_unavailable")
            name = attachment_name(answer.headers.get("content-disposition"), f"{file_id}.bin")
            return await answer.body(), name, content_type

        data, name, content_type = await self._browse(get)
        stored = await self._files.put(download_key(file_id, name), data)
        return DownloadedFile(
            file_id=file_id,
            filename=name,
            content_type=content_type.split(";")[0].strip(),
            size=stored.size,
            sha256=stored.sha256,
            storage_key=stored.key,
        )

    async def _html(self, url: str) -> str:
        """A page of the site through the HTML cache of 6 hours (§8.5)."""
        key = f"html/edisclosure/{hashlib.sha256(url.encode()).hexdigest()}"
        path = self._files.local_path(key)
        if await asyncio.to_thread(self._fresh, str(path)):
            return await asyncio.to_thread(path.read_text, encoding="utf-8")

        async def load(page: Page) -> str:
            await self._open(page, url)
            return sanitize(await page.content(), self._host)

        html = await self._browse(load)
        await self._files.put(key, html.encode())
        return html

    @staticmethod
    def _fresh(path: str) -> bool:
        try:
            return time.time() - os.stat(path).st_mtime < HTML_TTL.total_seconds()  # noqa: PTH116
        except FileNotFoundError:
            return False

    async def _browse[T](self, step: Callable[[Page], Awaitable[T]]) -> T:
        """Runs a step on the one page, retrying 5xx and timeouts of the site."""
        attempt = 0
        while True:
            async with self._lock:
                try:
                    page = await self._browser()
                    return await step(page)
                except (_Flaky, PlaywrightTimeout) as flaky:
                    reason = str(flaky) or "timeout"
                except PlaywrightError as error:
                    await self._close_browser()  # a crashed browser starts anew next time
                    raise TransientGatewayError("disclosure_unavailable") from error
            if attempt >= RETRIES:
                log.warning("edisclosure_unavailable", reason=reason)
                raise TransientGatewayError("disclosure_unavailable")
            await asyncio.sleep(backoff(attempt, None, 2.0))
            attempt += 1

    async def _open(self, page: Page, url: str) -> None:
        await self._pace(url)
        try:
            answer = await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_WAIT_MS)
        except PlaywrightError as error:
            # The JavaScript check reloads the page while goto waits for the first load.
            if "interrupted by another navigation" not in str(error):
                raise
            answer = None
        if answer is not None and answer.status >= 500:
            raise _Flaky(f"{url} answered {answer.status}")
        try:
            await page.wait_for_selector(
                f"{REAL_PAGE}, {BLOCK_PAGE}", state="attached", timeout=PAGE_WAIT_MS
            )
        except PlaywrightTimeout:
            if CAPTCHA_PATH not in page.url:
                raise  # a slow page: worth another try
        if CAPTCHA_PATH in page.url or await page.query_selector(BLOCK_PAGE):
            log.warning("edisclosure_blocked", captcha=CAPTCHA_PATH in page.url)
            raise TransientGatewayError("disclosure_unavailable")  # the adapter solves no captcha
        if "files.aspx" in page.url:
            with contextlib.suppress(PlaywrightError):  # a section may have no rows at all
                await page.wait_for_selector("table.files-table", state="attached", timeout=3000)

    async def _pace(self, url: str, *, robots: bool = True) -> None:
        if robots and self._robots is not None and not robots_allow(self._robots, url):
            raise PermanentGatewayError("forbidden")
        wait = self._next_at - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        self._next_at = time.monotonic() + self._delay_s

    async def _browser(self) -> Page:
        if self._page is None or self._page.is_closed():
            await self._close_browser()
            self._playwright = await async_playwright().start()
            self._context = await self._playwright.firefox.launch_persistent_context(
                self._profile, headless=False, locale="ru-RU", env=await self._display_env()
            )
            pages = self._context.pages
            self._page = pages[0] if pages else await self._context.new_page()
        if self._robots is None:
            await self._read_robots(self._page)
        return self._page

    async def _read_robots(self, page: Page) -> None:
        """robots.txt before anything else, RFC 9309: 4xx means no rules, 5xx means stop."""
        url = f"{self._base}/robots.txt"
        await self._pace(url)
        with contextlib.suppress(PlaywrightError):  # the browser passes the check here
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_WAIT_MS)
        await self._pace(url)
        answer = await page.context.request.get(url, timeout=PAGE_WAIT_MS)
        text = await answer.text()
        if answer.status == 200 and "user-agent" in text.lower():
            rules, delay = parse_robots(text)
        elif answer.status in {401, 403}:
            # The bot check, not a missing file: the rules stay unknown, so nothing goes out.
            raise TransientGatewayError("disclosure_unavailable")
        elif 400 <= answer.status < 500:
            rules, delay = [], 0.0
        else:
            raise _Flaky(f"robots.txt answered {answer.status}")
        self._robots, self._delay_s = rules, max(self._delay_s, delay)

    async def _display_env(self) -> dict[str, str | float | bool] | None:
        """No display on the server: a virtual one, since headless gets the captcha."""
        if sys.platform != "linux" or os.environ.get("DISPLAY"):
            return None
        if self._display is None or self._display.returncode is not None:  # none yet, or it died
            self._display = await asyncio.create_subprocess_exec(
                "Xvfb", ":99", "-screen", "0", "1280x1024x24", "-nolisten", "tcp",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )  # fmt: skip
            # ponytail: a fixed pause for Xvfb to listen; poll its socket if it ever races.
            await asyncio.sleep(1)
        return {**os.environ, "DISPLAY": ":99"}

    async def _close_browser(self) -> None:
        context, playwright = self._context, self._playwright
        self._page = self._context = self._playwright = None
        with contextlib.suppress(PlaywrightError):
            if context is not None:
                await context.close()
        if playwright is not None:
            await playwright.stop()
