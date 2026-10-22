"""The egress to Tavily (L-02; tech.md §3.5, §15.1): the static part of the xray config and the
xray service of the compose files."""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.xray_nodes import render

ROOT = Path(__file__).parents[4]
LINK = (
    "vless://00000000-0000-4000-8000-000000000001@192.0.2.10:443?encryption=none&fp=chrome"
    "&pbk=TestPublicKeyOfANodeTestPublicKeyOfANode000&security=reality&sid=0a"
    "&sni=www.example.com&type=tcp#Test"
)
PROXY_VARIABLES = {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}


def base() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(
        (ROOT / "infra" / "xray" / "base.json").read_text(encoding="utf-8")
    )
    return loaded


def services(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))
    return dict(loaded["services"])


def test_only_tavily_domains_reach_the_nodes() -> None:
    config = base()
    [inbound] = config["inbounds"]
    [blackhole] = config["outbounds"]  # nothing goes out directly from the base part
    [balancer] = config["routing"]["balancers"]
    first, last = config["routing"]["rules"][0], config["routing"]["rules"][-1]

    assert (inbound["tag"], inbound["protocol"], inbound["port"]) == ("tavily", "http", 8080)
    assert "accounts" not in inbound.get("settings", {})
    assert blackhole["protocol"] == "blackhole"
    assert (first["inboundTag"], first["domain"]) == (["tavily"], ["domain:tavily.com"])
    assert first["balancerTag"] == balancer["tag"]
    # Every other address, private ones too, ends in the blackhole, and so does a dead pool.
    assert len(config["routing"]["rules"]) == 2
    assert (last["network"], last["outboundTag"]) == ("tcp,udp", blackhole["tag"])
    assert balancer["fallbackTag"] == blackhole["tag"]


def test_the_rendered_nodes_fall_under_the_balancer_and_its_probes() -> None:
    config = base()
    [balancer] = config["routing"]["balancers"]
    tags = [str(node["tag"]) for node in render(LINK)[0]["outbounds"]]

    assert tags
    for selector in (balancer["selector"], config["observatory"]["subjectSelector"]):
        assert all(any(tag.startswith(prefix) for prefix in selector) for tag in tags)


def test_xray_publishes_no_port_and_the_api_gets_no_proxy_variables() -> None:
    vps = services("docker-compose.yml")
    xray, api = vps["xray"], vps["api"]
    environment = api.get("environment") or {}  # a map or a list of NAME=value
    names = [str(item).partition("=")[0].upper() for item in environment]

    assert "ports" not in xray
    assert "@sha256:" in xray["image"]
    assert {volume.split(":")[0] for volume in xray["volumes"]} == {
        "./xray/base.json",
        "./xray/nodes.json",
    }
    assert all(volume.endswith(":ro") for volume in xray["volumes"])
    assert not set(names) & PROXY_VARIABLES


@pytest.mark.parametrize("name", ["docker-compose.dev.yml", "docker-compose.ci.yml"])
def test_dev_and_ci_run_without_xray(name: str) -> None:
    assert "xray" not in services(name)
