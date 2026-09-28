import pytest

from scripts.check_forbidden_apis import is_scanned, scan_text

REAL_PY = "backend/app/gateways/tinvest/real.py"


@pytest.mark.parametrize(
    "code",
    [
        "from t_tech.invest.constants import INVEST_GRPC_API_SANDBOX\n",
        "# CONTRACT-GAP(F-07): stub until PortfolioOut gets a field\n",
        "await client.orders.get_orders(account_id=account)\n",
        "await client.stop_orders.get_stop_orders(account_id=account)\n",
        "await client.sandbox.open_sandbox_account()\n",
        "from t_tech.invest.sandbox.client import SandboxClient\n",
        "await api.post_order(figi=figi, quantity=1)\n",
        "await api.cancel_order(account_id=a, order_id=o)\n",
        "await api.replace_order(request)\n",
        "await api.post_stop_order(request)\n",
        "await api.cancel_stop_order(account_id=a, stop_order_id=s)\n",
        "stub: OrdersService\n",
        "stub: StopOrdersService\n",
        "stub: SandboxService\n",
    ],
)
def test_forbidden_python(code: str) -> None:
    assert scan_text(REAL_PY, code) != []


def test_contract_gap_marker_in_typescript() -> None:
    code = "// CONTRACT-GAP(F-09): local stub\nexport const x = 1;\n"
    assert scan_text("frontend/src/routes/(app)/portfolio/logic.ts", code) != []


def test_violation_reports_line_number() -> None:
    code = "import os\n\nfrom t_tech.invest.constants import INVEST_GRPC_API_SANDBOX\n"
    [violation] = scan_text(REAL_PY, code)
    assert f"{REAL_PY}:3" in violation


@pytest.mark.parametrize(
    "code",
    [
        "from t_tech.invest.constants import INVEST_GRPC_API\n",
        "accounts = await client.users.get_accounts()\n",
        "portfolio = await client.operations.get_portfolio(account_id=account)\n",
        "candles = client.get_all_candles(instrument_id=uid, from_=start)\n",
        "orders_total = 0  # not an API call\n",
    ],
)
def test_read_only_code_passes(code: str) -> None:
    assert scan_text(REAL_PY, code) == []


@pytest.mark.parametrize(
    "path",
    [
        "backend/app/gateways/tinvest/real.py",
        "frontend/src/lib/api/client.ts",
        "frontend/src/routes/(app)/portfolio/+page.svelte",
        "backend/fixtures/seed/llm/f07_overview.yaml",
        ".github/workflows/pr.yml",
    ],
)
def test_code_is_scanned(path: str) -> None:
    assert is_scanned(path)


@pytest.mark.parametrize(
    "path",
    [
        "tech.md",
        "CLAUDE.md",
        "docs/adr/0001-queue.md",
        "backend/uv.lock",
        "frontend/pnpm-lock.yaml",
        "scripts/check_forbidden_apis.py",
        "backend/tests/unit/scripts/test_check_forbidden_apis.py",
    ],
)
def test_docs_locks_and_the_checker_itself_are_skipped(path: str) -> None:
    assert not is_scanned(path)
