"""The portfolio tab (tech.md §6.4)."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.contracts.api.broker import AccountAlias
from app.contracts.api.portfolio import PortfolioOut
from app.domains.portfolio.deps import PortfolioServiceDep
from app.http.deps import CurrentUser

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("")
async def portfolio(
    user: CurrentUser,
    service: PortfolioServiceDep,
    account: Annotated[AccountAlias | None, Query()] = None,
) -> PortfolioOut:
    """Every visible account, or the one `account` names (acc1, acc2, …)."""
    return await service.portfolio(user.user_id, account)
