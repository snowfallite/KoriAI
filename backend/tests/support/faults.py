"""Fault plans for the fakes of the test app (tech.md §8.1, §14.2): `faults(FaultRule(...))`."""

import dataclasses
from collections.abc import Callable

import pytest
from fastapi import FastAPI

from app.contracts.faults import FaultPlan, FaultRule
from app.gateways.factory import Gateways
from app.gateways.fakes import Fake


def fakes(gateways: Gateways) -> list[Fake]:
    """Every fake of the app, the ones inside wrappers (the web budget) too."""
    found = []
    for field in dataclasses.fields(gateways):
        port = getattr(gateways, field.name)
        for candidate in (port, getattr(port, "inner", None)):
            if isinstance(candidate, Fake):
                found.append(candidate)
    return found


@pytest.fixture
def faults(app: FastAPI) -> Callable[..., FaultPlan]:
    """Gives every fake of the app one plan; a rule names the method it breaks."""

    def apply(*rules: FaultRule) -> FaultPlan:
        plan = FaultPlan(rules=list(rules))
        for fake in fakes(app.state.gateways):
            fake.plan = plan
        return plan

    return apply
