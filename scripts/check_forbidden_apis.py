"""Forbidden API guard: CONTRACT-GAP markers and T-Invest trading or sandbox APIs (§19.4)."""

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

SCANNED_SUFFIXES = frozenset(
    {".py", ".ts", ".js", ".mjs", ".cjs", ".svelte", ".html", ".css"}
    | {".yml", ".yaml", ".json", ".toml", ".sh"}
)

# The checker and its tests spell out every forbidden pattern.
SKIPPED = frozenset(
    {
        "scripts/check_forbidden_apis.py",
        "backend/tests/unit/scripts/test_check_forbidden_apis.py",
        "frontend/pnpm-lock.yaml",
    }
)

RULES = (
    (re.compile(r"CONTRACT-GAP"), "CONTRACT-GAP marker"),
    (re.compile(r"\bINVEST_GRPC_API_SANDBOX\b"), "T-Invest sandbox endpoint"),
    (re.compile(r"\.(?:orders|stop_orders|sandbox)\b"), "T-Invest trading or sandbox service"),
    (
        re.compile(r"\b(?:OrdersService|StopOrdersService|SandboxService)\b"),
        "T-Invest trading or sandbox service",
    ),
    (
        re.compile(
            r"\b(?:post_order|cancel_order|replace_order|post_stop_order|cancel_stop_order)\b"
        ),
        "T-Invest trading method",
    ),
)


def is_scanned(path: str) -> bool:
    return PurePosixPath(path).suffix in SCANNED_SUFFIXES and path not in SKIPPED


def scan_text(path: str, text: str) -> list[str]:
    return [
        f"{path}:{number}: {reason}: {line.strip()}"
        for number, line in enumerate(text.splitlines(), start=1)
        for pattern, reason in RULES
        if pattern.search(line)
    ]


def main() -> int:
    listed = subprocess.run(
        ["git", "ls-files", "-z"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    violations = [
        violation
        for path in listed.split("\0")
        if path and is_scanned(path) and Path(path).is_file()
        for violation in scan_text(path, Path(path).read_text(encoding="utf-8", errors="replace"))
    ]

    for violation in violations:
        sys.stderr.write(f"forbidden-apis: {violation}\n")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
