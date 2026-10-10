"""The portfolio of a user over the accounts they have not hidden (tech.md §6.4)."""

import asyncio
from collections.abc import Awaitable, Sequence
from decimal import Decimal
from uuid import UUID

import structlog
from pydantic import SecretStr

from app.contracts.api.portfolio import PortfolioOut
from app.contracts.common import Money
from app.contracts.tinvest import TPortfolio
from app.core import time
from app.core.errors import AppError, PermanentGatewayError
from app.domains.broker.service import Account, BrokerService
from app.domains.instruments.service import InstrumentsService
from app.domains.portfolio import mapping
from app.domains.portfolio.mapping import Holdings
from app.gateways.tinvest.port import TInvestPort

log = structlog.get_logger(__name__)


class PortfolioService:
    def __init__(
        self, broker: BrokerService, instruments: InstrumentsService, tinvest: TInvestPort
    ) -> None:
        self._broker = broker
        self._instruments = instruments
        self._tinvest = tinvest

    async def portfolio(self, user_id: UUID, account: str | None = None) -> PortfolioOut:
        """Every visible account, or the one with the alias `account`, valued in rubles."""
        token = await self._broker.get_token(user_id)
        accounts = await self._broker.visible_accounts(user_id)
        if account is not None:
            accounts = [found for found in accounts if found.alias == account]
            if not accounts:
                raise AppError("validation_error", "Нет такого счёта", {"account": account})
        holdings = await _all([self._holdings(token, found) for found in accounts])
        uids = [p.instrument_uid for held in holdings for p in held.portfolio.positions]
        instruments = await self._instruments.briefs(token, uids)
        needed = mapping.foreign_currencies(holdings, instruments)
        rates = await self._instruments.rub_rates(token, needed) if needed else {}
        if missing := sorted(needed - rates.keys()):
            log.warning("fx_rate_missing", currencies=missing)
            raise AppError(
                "tinvest_unavailable", f"Нет курса к рублю для пересчёта: {', '.join(missing)}"
            )
        found = mapping.portfolio_out(holdings, instruments, rates, time.now())
        log.info("portfolio_loaded", accounts=len(accounts), positions=len(found.positions))
        return found

    async def _holdings(self, token: SecretStr, account: Account) -> Holdings:
        try:
            portfolio = await self._tinvest.get_portfolio(token, account.external_id)
        except PermanentGatewayError as error:
            if error.code != "not_found":
                raise
            # A closed account may leave T-Invest: it holds nothing, the others still count.
            log.warning("portfolio_account_missing", account=account.alias)
            portfolio = TPortfolio(
                account_id=account.external_id,
                total=Money(amount=Decimal(0), currency=mapping.RUB),
                total_by_type={},
                expected_yield=None,
                expected_yield_pct=None,
                positions=[],
            )
        return Holdings(alias=account.alias, name=account.name, portfolio=portfolio)


async def _all[T](calls: Sequence[Awaitable[T]]) -> list[T]:
    """Runs the calls together; the first failure surfaces once every call has finished."""
    results = await asyncio.gather(*calls, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    return [result for result in results if not isinstance(result, BaseException)]
