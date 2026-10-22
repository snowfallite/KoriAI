"""The broker section of the Settings tab (tech.md §6.3)."""

from fastapi import APIRouter, Request

from app.contracts.api.broker import (
    AccountPatchIn,
    BrokerAccountOut,
    BrokerConnectIn,
    BrokerConnectionOut,
)
from app.domains.broker.deps import BrokerServiceDep
from app.http.deps import CurrentUser, client_ip

router = APIRouter(prefix="/api/broker", tags=["broker"])


@router.get("/connection")
async def connection(user: CurrentUser, broker: BrokerServiceDep) -> BrokerConnectionOut:
    return await broker.connection(user.user_id)


@router.put("/connection")
async def connect(
    body: BrokerConnectIn, user: CurrentUser, request: Request, broker: BrokerServiceDep
) -> BrokerConnectionOut:
    """Keeps the token only when T-Invest says it reads every account and does nothing more."""
    return await broker.connect(user.user_id, body.token, client_ip(request))


@router.post("/connection/verify")
async def verify(
    user: CurrentUser, request: Request, broker: BrokerServiceDep
) -> BrokerConnectionOut:
    """A token T-Invest refuses now leaves the connection with status invalid."""
    return await broker.verify(user.user_id, client_ip(request))


@router.delete("/connection", status_code=204)
async def disconnect(user: CurrentUser, request: Request, broker: BrokerServiceDep) -> None:
    await broker.disconnect(user.user_id, client_ip(request))


@router.patch("/accounts/{alias}")
async def change_account(
    alias: str, body: AccountPatchIn, user: CurrentUser, broker: BrokerServiceDep
) -> BrokerAccountOut:
    """A hidden account stays out of the portfolio and the agent."""
    return await broker.set_hidden(user.user_id, alias, body.is_hidden)
