"""The xray nodes of the owner's VLESS subscription (L-02; tech.md §15.1, §20.2) on made-up
links: no real id, key or address of a node goes into the repo."""

import base64
import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.xray_nodes import main, render

ID = "00000000-0000-4000-8000-000000000001"
KEY = "TestPublicKeyOfANodeTestPublicKeyOfANode000"  # made up, shaped like an x25519 key
TCP_VISION = (
    f"vless://{ID}@192.0.2.10:443?encryption=none&flow=xtls-rprx-vision&fp=firefox&pbk={KEY}"
    "&security=reality&sid=0a1b&sni=www.example.com&spx=%2Fstart&support-x25519mlkem768=true"
    "&type=tcp#%D0%90%D0%B2%D1%81%D1%82%D1%80%D0%B8%D1%8F"
)
TCP = (
    f"vless://{ID}@192.0.2.11:8443?encryption=none&fp=chrome&pbk={KEY}&security=reality&sid=0c"
    "&sni=www.example.org&type=tcp#Seychelles"
)
GRPC = (
    f"vless://{ID}@198.51.100.7:57366?authority=&encryption=none&fp=chrome&pbk={KEY}"
    "&security=reality&serviceName=&sid=1d2e&sni=www.example.net&spx=%2Fx&type=grpc#Netherlands"
)
LIST = f"{TCP_VISION}\n{TCP}\n{GRPC}\n"
ADDRESSES = ("192.0.2.", "198.51.100.")


def outbound(tag: str, address: str, port: int, stream: dict[str, object], **user: str) -> object:
    return {
        "tag": tag,
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": address,
                    "port": port,
                    "users": [{"id": ID, "encryption": "none", **user}],
                }
            ]
        },
        "streamSettings": stream,
    }


def reality(sni: str, fp: str, sid: str, spx: str) -> dict[str, object]:
    return {
        "serverName": sni,
        "fingerprint": fp,
        "publicKey": KEY,
        "shortId": sid,
        "spiderX": spx,
    }


def test_each_link_with_reality_over_tcp_or_grpc_becomes_an_outbound() -> None:
    nodes, warnings = render(LIST)

    assert nodes == {
        "outbounds": [
            outbound(
                "node-1",
                "192.0.2.10",
                443,
                {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": reality("www.example.com", "firefox", "0a1b", "/start"),
                },
                flow="xtls-rprx-vision",
            ),
            outbound(
                "node-2",
                "192.0.2.11",
                8443,
                {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": reality("www.example.org", "chrome", "0c", ""),
                },
            ),
            outbound(
                "node-3",
                "198.51.100.7",
                57366,
                {
                    "network": "grpc",
                    "security": "reality",
                    "realitySettings": reality("www.example.net", "chrome", "1d2e", "/x"),
                    "grpcSettings": {"serviceName": ""},
                },
            ),
        ]
    }
    assert warnings == []


@pytest.mark.parametrize(
    "encode",
    [
        lambda text: base64.b64encode(text.encode()).decode(),
        lambda text: base64.b64encode(text.encode()).decode().rstrip("="),
        lambda text: base64.urlsafe_b64encode(text.encode()).decode(),
        lambda text: base64.encodebytes(text.encode()).decode(),  # wrapped at 76 characters
        lambda text: text.replace("\n", "\r\n\r\n"),
    ],
    ids=["base64", "no padding", "url-safe", "wrapped", "crlf and blank lines"],
)
def test_base64_of_the_list_reads_like_the_list(encode: Callable[[str], str]) -> None:
    assert render(encode(LIST)) == render(LIST)


def test_other_links_are_skipped_naming_only_the_node() -> None:
    vmess = base64.b64encode(json.dumps({"add": "192.0.2.20", "id": ID}).encode()).decode()
    skipped = [
        f"vmess://{vmess}",
        f"trojan://{ID}@192.0.2.21:443?security=tls#Trojan",
        f"vless://{ID}@192.0.2.22:443?encryption=none&security=tls&sni=a.example&type=tcp#TLS",
        f"vless://{ID}@192.0.2.23:443?security=reality&pbk={KEY}&sni=a.example&type=ws#WS",
        f"vless://{ID}@192.0.2.24:443?security=reality&sni=a.example&type=tcp#NoKey",
        f"vless://{ID}@192.0.2.25?security=reality&pbk={KEY}&sni=a.example&type=tcp#NoPort",
        "not a link at all",
    ]

    nodes, warnings = render("\n".join([*skipped, TCP_VISION]))

    assert [node["tag"] for node in nodes["outbounds"]] == ["node-1"]
    assert len(warnings) == len(skipped)
    for name in ("Trojan", "TLS", "WS", "NoKey", "NoPort"):
        assert any(f"'{name}'" in warning for warning in warnings)
    text = "\n".join(warnings)
    assert ID not in text
    assert KEY not in text
    assert not any(address in text for address in ADDRESSES)


def test_the_name_of_a_node_is_decoded() -> None:
    _, warnings = render(TCP_VISION.replace("security=reality", "security=none"))

    assert warnings == ["skipped 'Австрия': security none"]


def test_no_subscription_writes_an_empty_list(tmp_path: Path) -> None:
    nodes = tmp_path / "nodes.json"

    assert main([str(tmp_path / "subscription"), str(nodes)]) == 0
    assert json.loads(nodes.read_text(encoding="utf-8")) == {"outbounds": []}


def test_a_subscription_writes_its_nodes_for_xray(tmp_path: Path) -> None:
    subscription, nodes = tmp_path / "subscription", tmp_path / "nodes.json"
    subscription.write_text(base64.b64encode(LIST.encode()).decode(), encoding="utf-8")

    assert main([str(subscription), str(nodes)]) == 0

    assert json.loads(nodes.read_text(encoding="utf-8")) == render(LIST)[0]
    if os.name == "posix":  # xray reads the file as uid 65532 inside its container
        assert nodes.stat().st_mode & 0o777 == 0o644


@pytest.mark.parametrize(
    "content",
    ["%%% neither links nor base64 %%%", "trojan://x@192.0.2.21:443#Trojan\n", "   \n"],
    ids=["garbage", "only unsupported links", "blank"],
)
def test_a_broken_subscription_keeps_the_nodes_xray_has(tmp_path: Path, content: str) -> None:
    subscription, nodes = tmp_path / "subscription", tmp_path / "nodes.json"
    subscription.write_text(LIST, encoding="utf-8")
    assert main([str(subscription), str(nodes)]) == 0
    before = nodes.read_bytes()
    subscription.write_text(content, encoding="utf-8")

    assert main([str(subscription), str(nodes)]) == 1
    assert nodes.read_bytes() == before


def test_the_same_nodes_leave_the_file_alone(tmp_path: Path) -> None:
    subscription, nodes = tmp_path / "subscription", tmp_path / "nodes.json"
    subscription.write_text(LIST, encoding="utf-8")
    assert main([str(subscription), str(nodes)]) == 0
    written = nodes.stat()

    assert main([str(subscription), str(nodes)]) == 0
    assert (nodes.stat().st_ino, nodes.stat().st_mtime_ns) == (written.st_ino, written.st_mtime_ns)
