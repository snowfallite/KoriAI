"""The xray nodes of the owner's VLESS subscription (tech.md §15.1, §20.2).

deploy.sh runs it on the VPS host, so it keeps to the standard library of Python 3.10:

    python3 xray_nodes.py SUBSCRIPTION NODES

SUBSCRIPTION holds the links one per line, or base64 of them as a subscription URL serves it.
Every vless:// link with reality over tcp or grpc becomes the outbound node-<n> of NODES; other
links are skipped with a warning that names only the node, since a link carries the account id
and the keys. Without SUBSCRIPTION the list is empty. A subscription that exists but gives no
node exits with 1 and keeps NODES as it was. NODES changes only when its content does.
"""

import argparse
import base64
import binascii
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

NETWORKS = ("tcp", "grpc")


class Skipped(ValueError):
    """A link that does not become an outbound; the message holds nothing of the link."""


def links(raw: str) -> list[str]:
    """The links of a subscription: plain lines, or base64 of them (padding and alphabet vary)."""
    text = raw.strip()
    if text and "://" not in text:
        compact = "".join(text.split()).replace("-", "+").replace("_", "/")
        try:
            text = base64.b64decode(compact + "=" * (-len(compact) % 4), validate=True).decode()
        except (binascii.Error, UnicodeDecodeError) as error:
            raise ValueError("the subscription is neither links nor base64 of links") from error
    return [line.strip() for line in text.splitlines() if line.strip()]


def name(link: str) -> str:
    """The node name of the link fragment: the only part of a link that is not a secret."""
    try:
        return unquote(urlsplit(link).fragment) or "unnamed"
    except ValueError:
        return "unnamed"


def outbound(link: str, tag: str) -> dict[str, object]:
    url = urlsplit(link)
    if url.scheme != "vless":
        raise Skipped(f"protocol {url.scheme or 'none'}")
    query = {key: values[-1] for key, values in parse_qs(url.query, keep_blank_values=True).items()}
    security, network = query.get("security", "none"), query.get("type", "tcp")
    if security != "reality":
        raise Skipped(f"security {security}")
    if network not in NETWORKS:
        raise Skipped(f"transport {network}")
    if query.get("encryption", "none") != "none":
        raise Skipped("vless encryption")
    try:
        port = url.port
    except ValueError:
        port = None
    if not url.username or not url.hostname or port is None:
        raise Skipped("no id, address or port")
    if not query.get("pbk") or not query.get("sni"):
        raise Skipped("reality without a public key or a server name")
    user: dict[str, str] = {"id": unquote(url.username), "encryption": "none"}
    if query.get("flow"):
        user["flow"] = query["flow"]
    stream: dict[str, object] = {
        "network": network,
        "security": "reality",
        "realitySettings": {
            "serverName": query["sni"],
            "fingerprint": query.get("fp") or "chrome",
            "publicKey": query["pbk"],
            "shortId": query.get("sid", ""),
            "spiderX": query.get("spx", ""),
        },
    }
    if network == "grpc":
        grpc: dict[str, object] = {"serviceName": query.get("serviceName", "")}
        if query.get("authority"):
            grpc["authority"] = query["authority"]
        if query.get("mode") == "multi":
            grpc["multiMode"] = True
        stream["grpcSettings"] = grpc
    return {
        "tag": tag,
        "protocol": "vless",
        "settings": {"vnext": [{"address": url.hostname, "port": port, "users": [user]}]},
        "streamSettings": stream,
    }


def render(raw: str) -> tuple[dict[str, list[dict[str, object]]], list[str]]:
    """The outbounds of a subscription and a warning for each link left out."""
    outbounds: list[dict[str, object]] = []
    warnings = []
    for link in links(raw):
        try:
            outbounds.append(outbound(link, f"node-{len(outbounds) + 1}"))
        except Skipped as why:
            warnings.append(f"skipped {name(link)!r}: {why}")
        except ValueError:  # urlsplit on a broken address: its message may quote the link
            warnings.append(f"skipped {name(link)!r}: unreadable link")
    return {"outbounds": outbounds}, warnings


def write(path: Path, text: str) -> None:
    """Replaces the file when its content changes. Mode 644: xray reads it as uid 65532 in its
    container, and /opt/kori (750) keeps it from the other users of the host."""
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".nodes-")
    with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file:
        file.write(text)
    Path(temporary).chmod(0o644)
    Path(temporary).replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("subscription", type=Path, help="links or base64 of them")
    parser.add_argument("nodes", type=Path, help="the outbounds file xray reads")
    args = parser.parse_args(argv)
    raw = args.subscription.read_text(encoding="utf-8") if args.subscription.exists() else None
    if raw is None:
        nodes: dict[str, list[dict[str, object]]] = {"outbounds": []}
        warnings: list[str] = ["no subscription: xray gets no node"]
    else:
        try:
            nodes, warnings = render(raw)
        except ValueError as error:
            sys.stderr.write(f"xray_nodes: {error}; the nodes stay as they were\n")
            return 1
        if not nodes["outbounds"]:
            for warning in [*warnings, "no node in the subscription; the nodes stay as they were"]:
                sys.stderr.write(f"xray_nodes: {warning}\n")
            return 1
    write(args.nodes, json.dumps(nodes, ensure_ascii=False, indent=2) + "\n")
    for warning in warnings:
        sys.stderr.write(f"xray_nodes: {warning}\n")
    sys.stderr.write(f"xray_nodes: nodes for xray: {len(nodes['outbounds'])}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
