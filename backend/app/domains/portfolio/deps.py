"""Providers of the portfolio domain (tech.md §16.1)."""

from typing import Annotated

from fastapi import Depends
from starlette.requests import HTTPConnection

from app.db.base import UnitOfWork
from app.domains.broker.service import BrokerService
from app.domains.instruments.service import InstrumentsService
from app.domains.portfolio.service import PortfolioService
from app.gateways.factory import Gateways


def portfolio_service(conn: HTTPConnection) -> PortfolioService:
    state = conn.app.state
    gateways: Gateways = state.gateways
    # A unit of work per service: one of them never nests in another's transaction.
    return PortfolioService(
        BrokerService(UnitOfWork(state.engine), state.settings),
        InstrumentsService(UnitOfWork(state.engine), gateways.tinvest),
        gateways.tinvest,
    )


PortfolioServiceDep = Annotated[PortfolioService, Depends(portfolio_service)]
