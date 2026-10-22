"""Providers of the broker domain (tech.md §16.1)."""

from typing import Annotated

from fastapi import Depends
from starlette.requests import HTTPConnection

from app.db.base import UnitOfWork
from app.domains.broker.service import BrokerService
from app.gateways.factory import Gateways


def broker_service(conn: HTTPConnection) -> BrokerService:
    state = conn.app.state
    gateways: Gateways = state.gateways
    return BrokerService(UnitOfWork(state.engine), state.settings, gateways.tinvest)


BrokerServiceDep = Annotated[BrokerService, Depends(broker_service)]
