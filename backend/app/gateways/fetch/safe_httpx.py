"""Image fetch of the media proxy (tech.md §3.5, §8.8): http(s) only, public addresses only,
at most 3 redirects with a check each, image/* only, at most max_bytes, 10 s."""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable

import httpx

from app.contracts.fetch import FetchedImage
from app.core.errors import PermanentGatewayError, TransientGatewayError

MAX_REDIRECTS = 3
TIMEOUT_S = 10.0

type Resolver = Callable[[str, int], Awaitable[list[str]]]


async def resolve(host: str, port: int) -> list[str]:
    try:
        found = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    return list(dict.fromkeys(str(info[4][0]) for info in found))


def is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])  # an IPv6 zone does not change the address
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    # is_global leaves out private, loopback, link-local, shared and reserved ranges.
    return ip.is_global and not ip.is_multicast


class SafeHttpxFetch:
    def __init__(
        self, *, transport: httpx.AsyncBaseTransport | None = None, resolver: Resolver = resolve
    ) -> None:
        # No proxies from the environment: they would connect where we did not check.
        self._http = httpx.AsyncClient(timeout=TIMEOUT_S, transport=transport, trust_env=False)
        self._resolve = resolver

    async def aclose(self) -> None:
        await self._http.aclose()

    async def fetch_image(self, url: str, *, max_bytes: int) -> FetchedImage:
        for _ in range(MAX_REDIRECTS + 1):
            target = httpx.URL(url)
            response = await self._send(target)
            try:
                if response.is_redirect:
                    url = str(target.join(response.headers.get("location", "")))
                    continue
                return await self._image(response, url, max_bytes)
            finally:
                await response.aclose()
        raise PermanentGatewayError("not_found")  # too many redirects

    async def _send(self, target: httpx.URL) -> httpx.Response:
        if target.scheme not in {"http", "https"} or not target.host:
            raise PermanentGatewayError("not_found")
        port = target.port or (443 if target.scheme == "https" else 80)
        addresses = await self._resolve(target.host, port)
        if not addresses:
            raise PermanentGatewayError("not_found")
        if not all(is_public(address) for address in addresses):
            raise PermanentGatewayError("forbidden")
        # Connect to the address just checked: a second lookup could rebind it (DNS rebinding).
        address = addresses[0]
        request = self._http.build_request(
            "GET",
            target.copy_with(host=address),
            headers={"Host": target.netloc.decode("ascii"), "Accept": "image/*"},
            extensions={"sni_hostname": target.host},  # TLS checks the name, not the address
        )
        try:
            return await self._http.send(request, stream=True)
        except httpx.TransportError as error:
            raise TransientGatewayError("web_unavailable") from error

    @staticmethod
    async def _image(response: httpx.Response, url: str, max_bytes: int) -> FetchedImage:
        if response.status_code >= 500:
            raise TransientGatewayError("web_unavailable")
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if response.status_code != 200 or not content_type.startswith("image/"):
            raise PermanentGatewayError("not_found")
        declared = response.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > max_bytes:
            raise PermanentGatewayError("not_found")
        data = bytearray()
        async for chunk in response.aiter_bytes():
            data += chunk
            if len(data) > max_bytes:
                raise PermanentGatewayError("not_found")
        return FetchedImage(content_type=content_type, data=bytes(data), final_url=url)
