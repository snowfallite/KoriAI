"""Core guard: zone labels and CORE_VERSION bumps (tech.md §19.4)."""

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from typing import Literal

Zone = Literal["contract", "general", "task"]

HAT_LABELS = frozenset({"owner", "contract-change", "core-impl"})

# Fixture files prefixed with a task ID (f07_*) belong to the task, not to the contract.
TASK_FIXTURE = re.compile(r"backend/fixtures/(?:.+/)?f\d{2}_[^/]*(?:/.+)?")

CONTRACT_ZONE = re.compile(
    r"tech\.md"
    r"|backend/app/contracts/.+"
    r"|backend/app/db/schema/.+"
    r"|backend/migrations/.+"
    r"|backend/app/config\.py"
    r"|\.env\.example"
    r"|backend/app/gateways/[^/]+/port\.py"
    r"|backend/fixtures/.+"
    r"|backend/app/domains/agent/routing\.py"
    r"|frontend/src/lib/(?:api|types)/.+"
    r"|frontend/src/lib/nav\.ts"
)

GENERAL_ZONE = re.compile(
    r"frontend/src/lib/(?:ui|components|utils|state)/.+"
    r"|frontend/src/app\.(?:css|html)"
    r"|frontend/src/routes/(?:\(app\)/)?\+layout\.[^/]+"
    r"|frontend/src/routes/\(auth\)/.+"
    r"|frontend/src/routes/\(app\)/dev/.+"
    r"|backend/app/(?:core|http|jobs|gateways)/.+"
    r"|backend/app/(?:main|cli)\.py"
    r"|backend/tests/support/.+"
    r"|(?:infra|\.github|\.claude|scripts)/.+"
    r"|docker-compose[^/]*\.yml"
    r"|justfile"
    r"|CLAUDE\.md"
    r"|docs/adr/.+"
)


def zone_of(path: str) -> Zone:
    if TASK_FIXTURE.fullmatch(path):
        return "task"
    if CONTRACT_ZONE.fullmatch(path):
        return "contract"
    if GENERAL_ZONE.fullmatch(path):
        return "general"
    return "task"


def core_version(core: str) -> int:
    match = re.search(r"^> CORE_VERSION: (\d+)$", core, re.MULTILINE)
    if match is None:
        raise ValueError("tech.md has no '> CORE_VERSION: N' line")
    return int(match.group(1))


def has_changelog_line(core: str, version: int) -> bool:
    return re.search(rf"^- v{version} \(\d{{4}}-\d{{2}}-\d{{2}}\)", core, re.MULTILINE) is not None


def evaluate(changed: Iterable[str], labels: set[str], base_core: str, head_core: str) -> list[str]:
    paths = sorted(set(changed))
    contract = [p for p in paths if zone_of(p) == "contract"]
    general = [p for p in paths if zone_of(p) == "general"]
    base, head = core_version(base_core), core_version(head_core)
    errors = []

    if head < base:
        errors.append(f"CORE_VERSION {head} is below main ({base}): rebase on origin/main")

    if contract:
        if not labels & {"contract-change", "core-impl"}:
            errors.append(
                "contract zone changed without a contract-change or core-impl label: "
                + ", ".join(contract)
            )
        if "contract-change" in labels:
            if head != base + 1:
                errors.append(f"contract-change needs CORE_VERSION {base + 1}, found {head}")
            if not has_changelog_line(head_core, base + 1):
                errors.append(
                    f"contract-change needs a Changelog line '- v{base + 1} (YYYY-MM-DD)'"
                )
        if "core-impl" in labels and "tech.md" in paths:
            errors.append("core-impl implements the current core: revert tech.md changes")

    if general and not labels & HAT_LABELS:
        errors.append(
            "general zone changed without an owner, contract-change or core-impl label: "
            + ", ".join(general)
        )

    return errors


def git(*args: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main", help="git ref the PR merges into")
    parser.add_argument("--labels", default="", help="comma-separated PR labels")
    args = parser.parse_args(argv)

    labels = {label.strip() for label in args.labels.split(",") if label.strip()}
    diff = git("diff", "--name-only", "--no-renames", "-z", f"{args.base}...HEAD")
    changed = [path for path in diff.split("\0") if path]
    errors = evaluate(
        changed, labels, git("show", f"{args.base}:tech.md"), git("show", "HEAD:tech.md")
    )

    for error in errors:
        sys.stderr.write(f"core-guard: {error}\n")
    if errors:
        return 1
    sys.stdout.write(f"core-guard: ok ({len(changed)} changed files)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
