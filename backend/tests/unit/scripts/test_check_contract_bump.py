import subprocess
from pathlib import Path

import pytest

from scripts.check_contract_bump import evaluate, main, zone_of


def core(version: int, *changelog: int) -> str:
    lines = [f"- v{v} (2026-09-26): change {v}." for v in changelog]
    return (
        "# tech.md\n\n"
        f"> CORE_VERSION: {version}\n"
        "> SKELETON_READY: no\n\n"
        "## Changelog (append-only, новые сверху)\n\n" + "\n".join(lines) + "\n"
    )


BASE = core(1, 1)
BUMPED = core(2, 2, 1)


@pytest.mark.parametrize(
    "path",
    [
        "tech.md",
        "backend/app/contracts/common.py",
        "backend/app/contracts/api/auth.py",
        "backend/app/db/schema/users.py",
        "backend/migrations/versions/20260926_1200_init.py",
        "backend/app/config.py",
        ".env.example",
        "backend/app/gateways/tinvest/port.py",
        "backend/fixtures/seed/users.yaml",
        "backend/fixtures/seed/llm/f7_overview.yaml",
        "backend/fixtures/reference/issuers.csv",
        "backend/app/domains/agent/routing.py",
        "frontend/src/lib/api/schema.d.ts",
        "frontend/src/lib/types/index.ts",
        "frontend/src/lib/nav.ts",
    ],
)
def test_contract_zone(path: str) -> None:
    assert zone_of(path) == "contract"


@pytest.mark.parametrize(
    "path",
    [
        "frontend/src/lib/ui/button/button.svelte",
        "frontend/src/lib/components/ChartView.svelte",
        "frontend/src/lib/utils/format.ts",
        "frontend/src/lib/state/run.svelte.ts",
        "frontend/src/app.css",
        "frontend/src/app.html",
        "frontend/src/routes/+layout.ts",
        "frontend/src/routes/+layout.svelte",
        "frontend/src/routes/(app)/+layout.ts",
        "frontend/src/routes/(auth)/login/+page.svelte",
        "frontend/src/routes/(app)/dev/kitchen-sink/+page.svelte",
        "backend/app/core/money.py",
        "backend/app/http/sse.py",
        "backend/app/main.py",
        "backend/app/jobs/app.py",
        "backend/app/cli.py",
        "backend/app/gateways/tinvest/fake.py",
        "backend/app/gateways/llm/gate.py",
        "backend/app/gateways/disclosure/edisclosure/parser.py",
        "backend/app/gateways/factory.py",
        "backend/tests/support/jobs.py",
        "infra/caddy/Caddyfile",
        ".github/workflows/pr.yml",
        ".claude/settings.json",
        "docker-compose.yml",
        "docker-compose.ci.yml",
        "scripts/smoke_external.py",
        "justfile",
        "CLAUDE.md",
        "docs/adr/0001-queue.md",
    ],
)
def test_general_zone(path: str) -> None:
    assert zone_of(path) == "general"


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "backend/app/domains/portfolio/service.py",
        "backend/app/domains/agent/graph.py",
        "backend/app/domains/agent/tools/calc.py",
        "backend/tests/unit/portfolio/test_weights.py",
        "backend/fixtures/seed/llm/f07_overview.yaml",
        "backend/fixtures/seed/web/f15_news.yaml",
        "backend/fixtures/seed/edisclosure/f10_sber/files.html",
        "frontend/src/routes/+page.svelte",
        "frontend/src/routes/(app)/portfolio/+page.svelte",
        "frontend/src/routes/(app)/chat/[[threadId]]/components/Composer.svelte",
        "frontend/tests/e2e/portfolio.spec.ts",
        "docs/sources/e-disclosure.md",
    ],
)
def test_task_zone(path: str) -> None:
    assert zone_of(path) == "task"


def test_trivial_readme_change_passes() -> None:
    assert evaluate(["README.md"], set(), BASE, BASE) == []


def test_task_fixture_needs_no_label() -> None:
    assert evaluate(["backend/fixtures/seed/llm/f07_overview.yaml"], set(), BASE, BASE) == []


def test_contract_zone_without_label_fails() -> None:
    assert evaluate(["backend/app/contracts/common.py"], set(), BASE, BASE) != []


def test_contract_zone_with_owner_label_fails() -> None:
    assert evaluate(["backend/app/contracts/common.py"], {"owner"}, BASE, BASE) != []


def test_core_impl_keeps_core_intact() -> None:
    changed = ["backend/app/contracts/common.py", "backend/app/db/schema/users.py"]
    assert evaluate(changed, {"core-impl"}, BASE, BASE) == []


def test_core_impl_with_core_edit_fails() -> None:
    changed = ["tech.md", "backend/app/contracts/common.py"]
    assert evaluate(changed, {"core-impl"}, BASE, BUMPED) != []


def test_contract_change_with_bump_and_changelog_passes() -> None:
    changed = ["tech.md", "backend/app/contracts/common.py"]
    assert evaluate(changed, {"contract-change"}, BASE, BUMPED) == []


def test_contract_change_without_bump_fails() -> None:
    changed = ["tech.md", "backend/app/contracts/common.py"]
    assert evaluate(changed, {"contract-change"}, BASE, core(1, 1)) != []


def test_contract_change_bump_by_two_fails() -> None:
    changed = ["tech.md", "backend/app/contracts/common.py"]
    assert evaluate(changed, {"contract-change"}, BASE, core(3, 3, 1)) != []


def test_contract_change_without_changelog_line_fails() -> None:
    changed = ["tech.md", "backend/app/contracts/common.py"]
    assert evaluate(changed, {"contract-change"}, BASE, core(2, 1)) != []


def test_changelog_line_of_another_version_does_not_count() -> None:
    changed = ["tech.md", "backend/app/contracts/common.py"]
    assert evaluate(changed, {"contract-change"}, BASE, core(2, 3, 1)) != []


def test_general_zone_without_label_fails() -> None:
    assert evaluate([".github/workflows/pr.yml"], set(), BASE, BASE) != []


@pytest.mark.parametrize("label", ["owner", "contract-change", "core-impl"])
def test_general_zone_with_hat_label_passes(label: str) -> None:
    assert evaluate([".github/workflows/pr.yml"], {label}, BASE, BASE) == []


def test_core_version_below_main_asks_for_rebase() -> None:
    errors = evaluate(["README.md"], set(), core(2, 2, 1), BASE)
    assert errors != []
    assert any("rebase" in error for error in errors)


def git(repo: Path, *args: str) -> None:
    identity = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run(  # noqa: S603
        ["git", *identity, *args],  # noqa: S607
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "tech.md").write_text(BASE, encoding="utf-8", newline="\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "core")
    git(tmp_path, "switch", "-c", "feature")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def commit_file(repo: Path, path: str, text: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", path)


def test_cli_fails_on_unlabelled_contract_change(repo: Path) -> None:
    commit_file(repo, "backend/app/contracts/common.py", "X = 1\n")
    assert main(["--base", "main", "--labels", ""]) == 1


def test_cli_passes_trivial_readme_pr(repo: Path) -> None:
    commit_file(repo, "README.md", "# kori\n")
    assert main(["--base", "main", "--labels", ""]) == 0


def test_cli_reads_bump_from_base_and_head(repo: Path) -> None:
    commit_file(repo, "tech.md", BUMPED)
    assert main(["--base", "main", "--labels", "contract-change"]) == 0
    assert main(["--base", "main", "--labels", "core-impl"]) == 1


def test_cli_checks_the_branch_head_not_the_merge_commit(repo: Path) -> None:
    # CI checks out a merge commit that already carries the newer core of main.
    commit_file(repo, "README.md", "# kori\n")
    git(repo, "switch", "main")
    commit_file(repo, "tech.md", BUMPED)
    git(repo, "switch", "--detach", "feature")
    git(repo, "merge", "--no-edit", "main")
    assert main(["--base", "main", "--head", "feature", "--labels", ""]) == 1
