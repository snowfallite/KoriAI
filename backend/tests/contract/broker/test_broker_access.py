"""What other domains get from broker.service (tech.md §3.5, §8.2): the token, opened only here, and
the accounts the user has not hidden. Runs on the seed in the test transaction."""

from uuid import UUID, uuid4

import pytest
import yaml
from fastapi import FastAPI
from pydantic import SecretBytes
from sqlalchemy import select, update

from app.core.errors import AppError
from app.db.base import UnitOfWork
from app.db.schema.broker import BrokerAccount
from app.db.schema.users import User
from app.domains.broker.service import BrokerService
from app.gateways.fixtures import SEED
from tests.support.seed import seed_user


def service(app: FastAPI) -> BrokerService:
    return BrokerService(UnitOfWork(app.state.engine), app.state.settings)


async def demo_id(app: FastAPI) -> UUID:
    async with UnitOfWork(app.state.engine) as session:
        found = await session.scalar(select(User.id).where(User.email == seed_user("user").email))
    assert found is not None
    return found


@pytest.mark.usefixtures("seeded")
async def test_the_token_opens_for_its_owner(app: FastAPI) -> None:
    token = await service(app).get_token(await demo_id(app))

    expected = seed_user("user").broker_token
    assert expected is not None
    assert token.get_secret_value() == expected.get_secret_value()


@pytest.mark.usefixtures("seeded")
async def test_a_user_without_a_connection_has_no_token(app: FastAPI) -> None:
    with pytest.raises(AppError) as refused:
        await service(app).get_token(uuid4())

    assert refused.value.code == "broker_not_connected"


@pytest.mark.usefixtures("seeded")
async def test_a_token_no_key_opens_counts_as_no_connection(app: FastAPI) -> None:
    # The key of the token left TINVEST_TOKEN_KEYS: the user has to connect again.
    other = {"k2": SecretBytes(bytes(32))}
    app.state.settings = app.state.settings.model_copy(
        update={"TINVEST_TOKEN_KEYS": other, "TINVEST_TOKEN_ACTIVE_KEY": "k2"}
    )

    with pytest.raises(AppError) as refused:
        await service(app).get_token(await demo_id(app))

    assert refused.value.code == "broker_not_connected"


@pytest.mark.usefixtures("seeded")
async def test_visible_accounts_leave_hidden_ones_out(app: FastAPI) -> None:
    seed = yaml.safe_load((SEED / "tinvest" / "accounts.yaml").read_text(encoding="utf-8"))
    by_opening = sorted(seed, key=lambda account: account["opened_date"])
    user_id = await demo_id(app)

    shown = await service(app).visible_accounts(user_id)
    async with UnitOfWork(app.state.engine) as session:
        await session.execute(
            update(BrokerAccount).where(BrokerAccount.alias == "acc1").values(is_hidden=True)
        )
    left = await service(app).visible_accounts(user_id)

    assert [(a.alias, a.name, a.external_id) for a in shown] == [
        (f"acc{n}", account["name"], account["id"]) for n, account in enumerate(by_opening, 1)
    ]
    assert [a.alias for a in left] == ["acc2"]
    assert await service(app).visible_accounts(uuid4()) == []
