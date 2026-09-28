"""e-disclosure discovery for S1-12 (tech.md §8.5, §22.1): what does a polite bot get?

Stage 1, access probe: robots.txt, the company search page, one company card, one file list and
one file, fetched with the KoriBot User-Agent at EDISCLOSURE_RPS. Pages and the request log land
in backend/tests/fixtures/edisclosure/, the file in .discovery/edisclosure/ (gitignored).
Hits the real site: run by hand with `just discover-edisclosure`.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT / "backend/tests/fixtures/edisclosure"
DOWNLOADS = ROOT / ".discovery/edisclosure"

# PJSC Sberbank: a card with a long IFRS file list.
PROBE_ID = 3043

# Browser check of ServicePipe that open-source crawlers reported in September 2026.
STUB = re.compile(rb"servicepipe|sp_rotated_captcha|spjs", re.IGNORECASE)

HEADERS = ("Server", "Content-Type", "Content-Disposition", "Retry-After")


def setting(key: str, default: str) -> str:
    """Read a key the way app/config.py does: the environment first, then the repo .env."""
    if key in os.environ:
        return os.environ[key]
    env = ROOT / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    pairs = (line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))
    return {k.strip(): v.strip() for k, v in pairs}.get(key, default)


class Crawler:
    def __init__(self, agent: str, delay: float) -> None:
        self.agent = agent
        self.delay = delay
        self.next_at = 0.0
        self.robots: RobotFileParser | None = None
        self.log: list[dict[str, object]] = []
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.opener.addheaders = [
            ("User-Agent", agent),
            ("Accept", "text/html,application/xhtml+xml,*/*;q=0.8"),
            ("Accept-Language", "ru,en;q=0.5"),
        ]

    def get(self, url: str, marker: re.Pattern[bytes]) -> tuple[int, bytes]:
        """Fetch one URL at the polite pace; the marker tells the real page from a stub."""
        if self.robots is not None and not self.robots.can_fetch(self.agent, url):
            self.log.append({"url": url, "verdict": "robots-disallowed"})
            return 0, b""
        time.sleep(max(0.0, self.next_at - time.monotonic()))
        self.next_at = time.monotonic() + self.delay
        try:
            with self.opener.open(url, timeout=120) as response:
                status, final, headers = response.status, response.url, response.headers
                body = response.read()
        except urllib.error.HTTPError as error:
            status, final, headers, body = error.code, error.url, error.headers, error.read()
        except OSError as error:
            self.log.append({"url": url, "verdict": "network-error", "error": str(error)})
            return 0, b""
        real = 200 <= status < 300 and marker.search(body) is not None
        cookies = headers.get_all("Set-Cookie")
        stub = bool(STUB.search(body))
        self.log.append(
            {
                "url": url,
                "final_url": final,
                "status": status,
                "verdict": "ok" if real else "stub" if stub else "blocked",
                "bytes": len(body),
                "headers": {k: headers[k] for k in HEADERS if headers[k]},
                # Names only: values are session state.
                "cookies": sorted({c.split("=", 1)[0] for c in cookies or []}),
            }
        )
        return status, body


def probe(crawler: Crawler, base: str) -> None:
    status, body = crawler.get(f"{base}/robots.txt", re.compile(rb"(?i)user-agent"))
    (SNAPSHOTS / "robots.txt").write_bytes(body)
    if status == 0 or status >= 500:
        # RFC 9309 §2.3.1.4: an unreachable robots.txt means a full disallow.
        return
    robots = RobotFileParser()
    if status < 300:
        robots.parse(body.decode("utf-8", "replace").splitlines())
    else:
        robots.allow_all = True  # RFC 9309 §2.3.1.3: 4xx means no rules.
    crawler.robots = robots
    crawler.delay = max(crawler.delay, float(robots.crawl_delay(crawler.agent) or 0))

    pages = {
        "search.html": (f"{base}/poisk-po-kompaniyam", rb"textfield"),
        f"company_{PROBE_ID}.html": (f"{base}/portal/company.aspx?id={PROBE_ID}", rb"files\.aspx"),
        f"files_{PROBE_ID}_4.html": (
            f"{base}/portal/files.aspx?id={PROBE_ID}&type=4",
            rb"(?i)FileLoad\.ashx",
        ),
    }
    for name, (url, marker) in pages.items():
        _, body = crawler.get(url, re.compile(marker))
        (SNAPSHOTS / name).write_bytes(body)

    file_ids = re.findall(rb"FileLoad\.ashx\?Fileid=(\d+)", body, re.IGNORECASE)
    if file_ids:
        file_id = file_ids[0].decode()
        _, data = crawler.get(
            f"{base}/portal/FileLoad.ashx?Fileid={file_id}", re.compile(rb"\A(?:PK\x03\x04|%PDF)")
        )
        DOWNLOADS.mkdir(parents=True, exist_ok=True)
        (DOWNLOADS / f"{file_id}.bin").write_bytes(data)
        crawler.log[-1]["magic"] = data[:8].hex()


def main() -> int:
    agent = setting("EDISCLOSURE_USER_AGENT", "")
    if not agent or "<" in agent:
        sys.stderr.write(
            "Set EDISCLOSURE_USER_AGENT with a real contact in .env or the environment, "
            "e.g. KoriBot/1.0 (+mailto:you@example.com)\n"
        )
        return 2
    base = setting("EDISCLOSURE_BASE_URL", "https://www.e-disclosure.ru").rstrip("/")
    crawler = Crawler(agent, 1 / float(setting("EDISCLOSURE_RPS", "0.5")))
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)

    probe(crawler, base)

    (SNAPSHOTS / "probe.json").write_text(
        json.dumps(crawler.log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for entry in crawler.log:
        sys.stdout.write(
            f"{entry.get('status', '-')!s:>3} {entry['verdict']:<18} "
            f"{entry.get('bytes', 0):>10,} B  {entry['url']}\n"
        )
    return 0 if all(entry["verdict"] == "ok" for entry in crawler.log) else 1


if __name__ == "__main__":
    sys.exit(main())
