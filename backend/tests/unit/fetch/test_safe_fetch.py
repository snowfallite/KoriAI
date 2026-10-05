"""The image fetch of the media proxy keeps to the SSRF rules of tech.md §3.5 (S1-09): public
addresses only, the address it checked is the one it connects to, 3 redirects checked each,
image/* only, at most max_bytes."""

from collections.abc import Callable

import httpx
import pytest

from app.core.errors import GatewayError, PermanentGatewayError, TransientGatewayError
from app.gateways.fetch.safe_httpx import SafeHttpxFetch, is_public

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
DNS = {
    "cdn.example.com": ["93.184.216.34"],
    "img.example.org": ["2606:2800:220:1:248:1893:25c8:1946"],
    "intranet.example.com": ["10.0.0.5"],
    "mixed.example.com": ["93.184.216.34", "192.168.1.10"],
    "metadata.example.com": ["169.254.169.254"],
    "127.0.0.1": ["127.0.0.1"],
    "xn--e1afmkfd.xn--p1ai": ["93.184.216.35"],  # пример.рф
}

type Handler = Callable[[httpx.Request], httpx.Response]


async def resolver(host: str, port: int) -> list[str]:
    return DNS.get(host, [])


def image(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, headers={"Content-Type": "image/png"}, content=PNG)


def fetcher(handler: Handler, sent: list[httpx.Request] | None = None) -> SafeHttpxFetch:
    def record(request: httpx.Request) -> httpx.Response:
        if sent is not None:
            sent.append(request)
        return handler(request)

    return SafeHttpxFetch(transport=httpx.MockTransport(record), resolver=resolver)


async def test_a_public_image_comes_from_the_address_that_was_checked() -> None:
    sent: list[httpx.Request] = []

    found = await fetcher(image, sent).fetch_image(
        "https://cdn.example.com/logo.png", max_bytes=1024
    )

    assert (found.content_type, found.data, found.final_url) == (
        "image/png",
        PNG,
        "https://cdn.example.com/logo.png",
    )
    [request] = sent
    # Pinned to the checked address: no second lookup to rebind.
    assert (request.url.host, request.url.path) == ("93.184.216.34", "/logo.png")
    assert request.headers["host"] == "cdn.example.com"
    assert request.extensions["sni_hostname"] == "cdn.example.com"


async def test_a_cyrillic_domain_goes_out_in_punycode() -> None:
    sent: list[httpx.Request] = []

    await fetcher(image, sent).fetch_image("https://пример.рф/лого.png", max_bytes=1024)

    assert sent[0].url.host == "93.184.216.35"
    assert sent[0].headers["host"] == "xn--e1afmkfd.xn--p1ai"
    assert sent[0].extensions["sni_hostname"] == "xn--e1afmkfd.xn--p1ai"


async def test_no_cookie_of_one_site_follows_the_next_request() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        headers = {"Content-Type": "image/png", "Set-Cookie": "session=secret; Path=/"}
        return httpx.Response(200, headers=headers, content=PNG)

    fetch = fetcher(handler, sent)
    await fetch.fetch_image("https://cdn.example.com/a.png", max_bytes=1024)
    await fetch.fetch_image("https://cdn.example.com/b.png", max_bytes=1024)

    assert "cookie" not in sent[1].headers


async def test_an_ipv6_address_goes_into_the_url_as_is() -> None:
    sent: list[httpx.Request] = []

    await fetcher(image, sent).fetch_image("http://img.example.org/a.png", max_bytes=1024)

    assert sent[0].url.host == "2606:2800:220:1:248:1893:25c8:1946"


@pytest.mark.parametrize(
    "url",
    [
        "http://intranet.example.com/a.png",
        "http://mixed.example.com/a.png",  # one private record is enough
        "http://metadata.example.com/latest/meta-data/",
        "http://127.0.0.1/a.png",
    ],
)
async def test_private_loopback_and_link_local_addresses_are_refused(url: str) -> None:
    sent: list[httpx.Request] = []

    with pytest.raises(PermanentGatewayError) as refused:
        await fetcher(image, sent).fetch_image(url, max_bytes=1024)

    assert refused.value.code == "forbidden"
    assert sent == []  # refused before any connection


async def test_a_redirect_to_a_private_address_is_refused() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://intranet.example.com/secret.png"})

    with pytest.raises(PermanentGatewayError) as refused:
        await fetcher(handler, sent).fetch_image("https://cdn.example.com/a.png", max_bytes=1024)

    assert refused.value.code == "forbidden"
    assert [r.headers["host"] for r in sent] == ["cdn.example.com"]


async def test_a_relative_redirect_is_followed_and_checked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old.png":
            return httpx.Response(301, headers={"Location": "/new.png"})
        return image(request)

    found = await fetcher(handler).fetch_image("https://cdn.example.com/old.png", max_bytes=1024)

    assert found.final_url == "https://cdn.example.com/new.png"


async def test_a_fourth_redirect_is_too_many() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": f"{request.url.path}x"})

    with pytest.raises(PermanentGatewayError):
        await fetcher(handler, sent).fetch_image("https://cdn.example.com/a", max_bytes=1024)

    assert len(sent) == 4  # the request and three redirects


@pytest.mark.parametrize(
    ("url", "handler", "max_bytes"),
    [
        ("file:///etc/passwd", image, 1024),
        ("ftp://cdn.example.com/a.png", image, 1024),
        ("https://unknown.example.com/a.png", image, 1024),
        (
            "https://cdn.example.com/page",
            lambda r: httpx.Response(200, headers={"Content-Type": "text/html"}, content=b"<p>"),
            1024,
        ),
        ("https://cdn.example.com/a.png", image, len(PNG) - 1),
        (
            "https://cdn.example.com/a.png",
            lambda r: httpx.Response(404, headers={"Content-Type": "image/png"}),
            1024,
        ),
    ],
    ids=["file", "ftp", "no address", "not an image", "too big", "404"],
)
async def test_what_is_not_an_image_within_limits_is_not_found(
    url: str, handler: Handler, max_bytes: int
) -> None:
    with pytest.raises(PermanentGatewayError) as missing:
        await fetcher(handler).fetch_image(url, max_bytes=max_bytes)

    assert missing.value.code == "not_found"


async def test_a_size_without_content_length_is_counted_while_reading() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        stream = httpx.ByteStream(PNG * 100)  # no Content-Length to trust
        return httpx.Response(200, headers={"Content-Type": "image/png"}, stream=stream)

    with pytest.raises(PermanentGatewayError):
        await fetcher(handler).fetch_image("https://cdn.example.com/a.png", max_bytes=len(PNG) * 10)


async def test_a_server_error_may_pass() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with pytest.raises(TransientGatewayError) as unavailable:
        await fetcher(handler).fetch_image("https://cdn.example.com/a.png", max_bytes=1024)

    assert unavailable.value.code == "web_unavailable"
    assert isinstance(unavailable.value, GatewayError)


@pytest.mark.parametrize(
    ("address", "public"),
    [
        ("93.184.216.34", True),
        ("2606:2800:220:1:248:1893:25c8:1946", True),
        ("10.1.2.3", False),
        ("172.16.0.1", False),
        ("192.168.0.1", False),
        ("127.0.0.1", False),
        ("::1", False),
        ("169.254.169.254", False),
        ("fe80::1%eth0", False),
        ("100.64.0.1", False),  # shared address space of carriers
        ("::ffff:127.0.0.1", False),  # loopback inside an IPv6 form
        ("224.0.0.1", False),
        ("0.0.0.0", False),  # noqa: S104 - the address under test
    ],
)
def test_public_addresses(address: str, public: bool) -> None:
    assert is_public(address) is public
